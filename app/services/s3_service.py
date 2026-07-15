"""Lecture des fichiers Parquet depuis le bucket S3 silver.

Structure réelle du bucket (partitionnée par velhot-transform-dev) :
  velhot-silver-dev/
    status/station_id={id}/date={YYYY-MM-DD}/data.parquet
    predictions/date={YYYY-MM-DD}/...        (écrit par velhot-train-model-dev)

Colonnes status réelles : station_id, name, lat, lon, address, capacity,
timestamp, fill_rate, bikes_available, docks_available, bikes_disabled,
docks_disabled, status, last_reported, hour, hour_sin, hour_cos, dow,
dow_sin, dow_cos, is_weekend.
"""
import io
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from typing import Optional

import boto3
import pandas as pd
import pyarrow.parquet as pq
from botocore.exceptions import BotoCoreError, ClientError, NoCredentialsError

from app.config import settings
from app.exceptions import DataSourceUnavailable
from app.logging_config import get_logger

logger = get_logger(__name__)


def _get_s3():
    return boto3.client("s3", region_name=settings.AWS_REGION)


def _list_objects(prefix: str) -> list[dict]:
    try:
        s3 = _get_s3()
        paginator = s3.get_paginator("list_objects_v2")
        objects = []
        for page in paginator.paginate(Bucket=settings.S3_BUCKET_SILVER, Prefix=prefix):
            objects.extend(page.get("Contents", []))
        return objects
    except NoCredentialsError as e:
        logger.error("Credentials AWS manquants : %s", e)
        raise DataSourceUnavailable("S3", "Credentials AWS non configurés") from e
    except ClientError as e:
        logger.error("Erreur S3 (%s) : %s", prefix, e)
        raise DataSourceUnavailable("S3", f"Accès refusé ou bucket introuvable : {e}") from e
    except BotoCoreError as e:
        logger.error("Erreur réseau S3 : %s", e)
        raise DataSourceUnavailable("S3", "Connexion à S3 impossible") from e


def _read_parquet(key: str, columns: Optional[list[str]] = None) -> pd.DataFrame:
    try:
        s3 = _get_s3()
        body = s3.get_object(Bucket=settings.S3_BUCKET_SILVER, Key=key)["Body"].read()
        buf = io.BytesIO(body)
        if columns is not None:
            # Ne lire que les colonnes demandées : divise la mémoire et le temps
            # de parsing (les fichiers status ont 20+ colonnes dont plusieurs
            # lourdes/inutiles ici : address, temp, precip, last_reported...).
            # Repli sur une lecture complète si un fichier n'a pas ces colonnes.
            try:
                pf = pq.ParquetFile(buf)
                avail = [c for c in columns if c in pf.schema_arrow.names]
                return pf.read(columns=avail).to_pandas()
            except Exception:
                buf.seek(0)
        return pq.read_table(buf).to_pandas()
    except ClientError as e:
        # NoSuchKey est attendu : une station peut ne pas avoir de relevé pour
        # la date demandée (clé construite à partir de la liste des station_id).
        if e.response.get("Error", {}).get("Code") == "NoSuchKey":
            logger.debug("Aucun fichier pour %s", key)
        else:
            logger.warning("Lecture impossible %s : %s", key, e)
        return pd.DataFrame()
    except Exception as e:
        logger.warning("Fichier Parquet illisible %s : %s", key, e)
        return pd.DataFrame()


# --- Liste des station_id (mise en cache) --------------------------------
# Le layout status/station_id={id}/date={date}/ empêche de préfixer par date.
# Lister status/ sans délimiteur ramène TOUS les fichiers de TOUTES les dates
# (des dizaines de milliers d'objets, coût croissant dans le temps).
# On liste uniquement les préfixes station_id=* (Delimiter="/") : borné à ~463
# entrées, ~15x plus rapide. La liste des stations change très rarement -> cache.
_STATION_IDS_CACHE: Optional[list[str]] = None
_STATION_IDS_CACHE_TIME: Optional[datetime] = None
_STATION_IDS_TTL = timedelta(hours=6)


def _list_station_ids() -> list[str]:
    global _STATION_IDS_CACHE, _STATION_IDS_CACHE_TIME
    now = datetime.now(timezone.utc)
    if (
        _STATION_IDS_CACHE is not None
        and _STATION_IDS_CACHE_TIME is not None
        and now - _STATION_IDS_CACHE_TIME < _STATION_IDS_TTL
    ):
        return _STATION_IDS_CACHE

    try:
        s3 = _get_s3()
        paginator = s3.get_paginator("list_objects_v2")
        ids: list[str] = []
        for page in paginator.paginate(
            Bucket=settings.S3_BUCKET_SILVER, Prefix="status/", Delimiter="/"
        ):
            for cp in page.get("CommonPrefixes", []):
                # cp["Prefix"] == "status/station_id=<id>/"
                prefix = cp["Prefix"]
                if "station_id=" in prefix:
                    ids.append(prefix.split("station_id=")[1].rstrip("/"))
    except NoCredentialsError as e:
        logger.error("Credentials AWS manquants : %s", e)
        raise DataSourceUnavailable("S3", "Credentials AWS non configurés") from e
    except ClientError as e:
        logger.error("Erreur S3 (liste stations) : %s", e)
        raise DataSourceUnavailable("S3", f"Accès refusé ou bucket introuvable : {e}") from e
    except BotoCoreError as e:
        logger.error("Erreur réseau S3 : %s", e)
        raise DataSourceUnavailable("S3", "Connexion à S3 impossible") from e

    _STATION_IDS_CACHE = ids
    _STATION_IDS_CACHE_TIME = now
    return ids


# Colonnes réellement exploitées par _row_to_station_dict / snapshot.
# On exclut address, temp, precip, last_reported, bikes/docks_disabled, dow :
# inutiles ici et coûteuses en mémoire (surtout les colonnes texte).
_SNAPSHOT_COLUMNS = [
    "station_id", "name", "lat", "lon", "capacity", "timestamp", "fill_rate",
    "bikes_available", "docks_available", "status",
    "hour", "hour_sin", "hour_cos", "dow_sin", "dow_cos", "is_weekend",
]

# Concurrence bornée : 100 lectures simultanées matérialisaient jusqu'à 100
# corps de fichiers + DataFrames en RAM -> OOM sur le conteneur 1 Go. 24
# suffit à saturer les I/O S3 sans faire exploser la mémoire.
_READ_WORKERS = 32


def _read_status_for_date(date_str: str, columns: Optional[list[str]] = None) -> pd.DataFrame:
    """Lit tous les fichiers status/station_id=*/date={date_str}/data.parquet.

    Construit les clés directement à partir de la liste (cachée) des station_id,
    au lieu de lister — puis filtrer — tous les objets de status/.
    """
    keys = [
        f"status/station_id={sid}/date={date_str}/data.parquet"
        for sid in _list_station_ids()
    ]
    return _read_keys(keys, columns)


def _read_keys(keys: list[str], columns: Optional[list[str]] = None) -> pd.DataFrame:
    def _read(k: str) -> pd.DataFrame:
        return _read_parquet(k, columns)

    with ThreadPoolExecutor(max_workers=_READ_WORKERS) as executor:
        dfs = list(executor.map(_read, keys))

    dfs = [d for d in dfs if not d.empty]
    return pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()


def _read_today_status() -> pd.DataFrame:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    df = _read_status_for_date(today)
    if df.empty:
        logger.warning("Aucune donnée status pour %s dans s3://%s/status/", today, settings.S3_BUCKET_SILVER)
    return df


def _read_predictions_for_date(date_str: str) -> pd.DataFrame:
    """Lit les prédictions de la couche gold pour une date.

    Le layout est predictions/date={date}/data.parquet (un seul fichier pour
    toutes les stations) : on lit la clé directement. En repli (sous-partitions
    éventuelles), on liste puis lit ce qui correspond à la date.
    """
    df = _read_parquet(f"predictions/date={date_str}/data.parquet")
    if not df.empty:
        return df

    objects = _list_objects(f"predictions/date={date_str}/")
    keys = [o["Key"] for o in objects if o["Key"].endswith(".parquet")]
    if not keys:
        return pd.DataFrame()
    with ThreadPoolExecutor(max_workers=100) as executor:
        dfs = list(executor.map(_read_parquet, keys))
    dfs = [d for d in dfs if not d.empty]
    return pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()


# Cache des prédictions : la couche gold est régénérée toutes les ~15 min.
# Une TTL de 5 min (cadence d'ingestion) évite de relire S3 à chaque requête
# (endpoints /predict, /predict/{id} et /alerts partagent le même cache).
_PREDICTIONS_CACHE: Optional[pd.DataFrame] = None
_PREDICTIONS_CACHE_TIME: Optional[datetime] = None
_PREDICTIONS_TTL = timedelta(minutes=5)


def _read_today_predictions() -> pd.DataFrame:
    global _PREDICTIONS_CACHE, _PREDICTIONS_CACHE_TIME
    now = datetime.now(timezone.utc)
    if (
        _PREDICTIONS_CACHE is not None
        and _PREDICTIONS_CACHE_TIME is not None
        and now - _PREDICTIONS_CACHE_TIME < _PREDICTIONS_TTL
    ):
        return _PREDICTIONS_CACHE

    today = now.strftime("%Y-%m-%d")
    df = _read_predictions_for_date(today)
    if df.empty:
        logger.warning("Aucune prédiction pour %s dans s3://%s/predictions/", today, settings.S3_BUCKET_SILVER)
        if _PREDICTIONS_CACHE is not None:
            return _PREDICTIONS_CACHE
        return df

    _PREDICTIONS_CACHE = df
    _PREDICTIONS_CACHE_TIME = now
    return df


def _to_iso(ts) -> str:
    if isinstance(ts, pd.Timestamp):
        return ts.isoformat()
    return str(ts)


def _row_to_station_dict(row: pd.Series) -> dict:
    """Mappe une ligne du Parquet silver vers le format StationOut attendu par l'API."""
    return {
        "station_id": str(row["station_id"]),
        "name": row.get("name", ""),
        "lat": float(row.get("lat", 0.0)),
        "lon": float(row.get("lon", 0.0)),
        "capacity": int(row.get("capacity", 0)),
        "num_bikes_available": int(row.get("bikes_available", 0)),
        "num_docks_available": int(row.get("docks_available", 0)),
        "fill_rate": float(row.get("fill_rate", 0.0)),
        "status": str(row.get("status", "OPEN")),
        "hour": int(row.get("hour", 0)),
        "hour_sin": float(row.get("hour_sin", 0.0)),
        "hour_cos": float(row.get("hour_cos", 0.0)),
        "dow_sin": float(row.get("dow_sin", 0.0)),
        "dow_cos": float(row.get("dow_cos", 0.0)),
        "is_weekend": bool(row.get("is_weekend", 0)),
        "timestamp": _to_iso(row.get("timestamp")),
    }


_STATIONS_CACHE = None
_STATIONS_CACHE_TIME = None


def get_all_stations() -> list[dict]:
    """Toutes les stations — dernière lecture du jour par station_id, avec cache in-memory configurable."""
    global _STATIONS_CACHE, _STATIONS_CACHE_TIME
    
    now = datetime.now(timezone.utc)
    if (
        _STATIONS_CACHE is not None 
        and _STATIONS_CACHE_TIME is not None 
        and (now - _STATIONS_CACHE_TIME).total_seconds() < settings.STATIONS_CACHE_TTL
    ):
        logger.info(
            "Retour des stations depuis le cache in-memory (TTL %ds restant: %ds)", 
            settings.STATIONS_CACHE_TTL,
            int(settings.STATIONS_CACHE_TTL - (now - _STATIONS_CACHE_TIME).total_seconds())
        )
        return _STATIONS_CACHE

    df = _read_today_status()
    if df.empty:
        if _STATIONS_CACHE:
            logger.warning("Erreur lecture S3, retour des stations obsolètes du cache")
            return _STATIONS_CACHE
        return []
    df = df.sort_values("timestamp").drop_duplicates("station_id", keep="last")
    stations = [_row_to_station_dict(row) for _, row in df.iterrows()]
    
    _STATIONS_CACHE = stations
    _STATIONS_CACHE_TIME = now
    logger.info("Cache in-memory des stations mis à jour (%d stations)", len(stations))
    return stations


# Cache du DataFrame brut d'une journée complète (toutes stations, tous
# relevés intra-journaliers), indexé par date. Sert au slider temporel :
# le playback rejoue la journée sans relire S3 à chaque pas. TTL court pour
# le jour courant (nouveaux relevés toutes les ~5 min) ; les jours passés
# sont immuables mais on garde la même TTL par simplicité.
_DAY_STATUS_CACHE: dict[str, tuple[pd.DataFrame, datetime]] = {}
_DAY_STATUS_TTL = timedelta(minutes=5)


def _get_day_status(date_str: str) -> pd.DataFrame:
    now = datetime.now(timezone.utc)
    cached = _DAY_STATUS_CACHE.get(date_str)
    if cached is not None and now - cached[1] < _DAY_STATUS_TTL:
        return cached[0]

    df = _read_status_for_date(date_str, columns=_SNAPSHOT_COLUMNS)
    if df.empty and cached is not None:
        # Lecture S3 vide (erreur transitoire) : on garde le cache existant.
        return cached[0]
    _DAY_STATUS_CACHE[date_str] = (df, now)
    return df


def get_stations_snapshot(at: datetime) -> list[dict]:
    """État de toutes les stations à l'instant `at` (dernier relevé <= at ce jour).

    Alimente le slider temporel du frontend : pour chaque station, on renvoie
    le relevé le plus récent dont le timestamp ne dépasse pas `at`.
    """
    if at.tzinfo is None:
        at = at.replace(tzinfo=timezone.utc)
    at = at.astimezone(timezone.utc)

    df = _get_day_status(at.strftime("%Y-%m-%d"))
    if df.empty:
        logger.warning("Aucune donnée status pour le snapshot à %s", at.isoformat())
        return []

    ts = pd.to_datetime(df["timestamp"], utc=True)
    df = df[ts <= at]
    if df.empty:
        # `at` est antérieur au premier relevé du jour : rien à montrer.
        return []

    df = df.sort_values("timestamp").drop_duplicates("station_id", keep="last")
    return [_row_to_station_dict(row) for _, row in df.iterrows()]


def get_station_by_id(station_id: str) -> Optional[dict]:
    # Si le cache des stations est chaud, on sert depuis celui-ci (aucune
    # lecture S3). Sinon on lit le seul fichier de la station (1 objet).
    if _STATIONS_CACHE is not None and _STATIONS_CACHE_TIME is not None:
        last_pull = get_latest_pull_time(datetime.now(timezone.utc))
        if _STATIONS_CACHE_TIME >= last_pull:
            for st in _STATIONS_CACHE:
                if st["station_id"] == str(station_id):
                    return st

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    key = f"status/station_id={station_id}/date={today}/data.parquet"
    df = _read_parquet(key)
    if df.empty:
        return None
    rows = df.sort_values("timestamp")
    return _row_to_station_dict(rows.iloc[-1])


def get_predictions(station_id: Optional[str] = None) -> list[dict]:
    """Lit predictions/ pré-calculées (utilisé par /alerts)."""
    df = _read_today_predictions()
    if df.empty:
        return []
    if station_id is not None:
        df = df[df["station_id"].astype(str) == str(station_id)]
    return df.to_dict(orient="records")


def warm_caches() -> None:
    """Précharge les caches lourds (snapshot du jour + peak-hours) au démarrage.

    Appelé dans un thread d'arrière-plan : les premières requêtes utilisateur
    tombent alors sur du cache chaud (< quelques ms), ce qui garantit des temps
    de réponse bien sous 5 s même pour le tout premier appel externe.
    """
    now = datetime.now(timezone.utc)
    try:
        _get_day_status(now.strftime("%Y-%m-%d"))
        logger.info("warm_caches: snapshot du jour préchargé")
    except Exception as e:  # noqa: BLE001 - le warmup ne doit jamais crasher l'app
        logger.warning("warm_caches: échec préchargement snapshot : %s", e)
    try:
        get_peak_hours_s3()
        logger.info("warm_caches: peak-hours (S3) préchargé")
    except Exception as e:  # noqa: BLE001
        logger.warning("warm_caches: échec préchargement peak-hours S3 : %s", e)

    # Préchauffe aussi le cache Athena : la requête froide (~4-5 s) est ainsi
    # payée au démarrage, pas par le premier appel utilisateur (< 5 s garanti).
    # Import local pour éviter tout cycle d'import.
    from app.services import athena_service
    for label, fn in (("peak-hours", athena_service.get_peak_hours),
                      ("heatmap", athena_service.get_heatmap)):
        try:
            fn()
            logger.info("warm_caches: %s (Athena) préchargé", label)
        except Exception as e:  # noqa: BLE001
            logger.warning("warm_caches: échec préchargement %s Athena : %s", label, e)


def get_alerts(threshold_empty: float = 0.1, threshold_full: float = 0.9) -> list[dict]:
    preds = get_predictions()
    alerts = []
    for p in preds:
        t30 = p.get("pred_t30", p.get("t30"))
        if t30 is None:
            continue
        if t30 < threshold_empty:
            alerts.append({
                "station_id": str(p["station_id"]),
                "type": "EMPTY",
                "horizon": "30min",
                "predicted_fill_rate": round(float(t30), 4),
            })
        elif t30 > threshold_full:
            alerts.append({
                "station_id": str(p["station_id"]),
                "type": "FULL",
                "horizon": "30min",
                "predicted_fill_rate": round(float(t30), 4),
            })
    return alerts


# Cache du résultat peak-hours : profil horaire moyen très stable (évolue de
# façon marginale d'un jour à l'autre). TTL longue -> le calcul lourd ne tourne
# qu'une fois par heure au plus, les autres requêtes sont instantanées.
_PEAK_HOURS_CACHE: Optional[list[dict]] = None
_PEAK_HOURS_CACHE_TIME: Optional[datetime] = None
_PEAK_HOURS_TTL = timedelta(hours=1)

# Le fill_rate moyen par heure ne nécessite pas TOUTES les stations : un
# échantillon réparti (~100 stations sur ~463) donne la même courbe à
# <0.5 % près, pour ~4.5x moins de fichiers à lire. Ancré (stride) pour rester
# déterministe entre appels et par rapport au cache.
_PEAK_HOURS_SAMPLE = 100


def get_peak_hours_s3() -> list[dict]:
    """Fill_rate moyen par heure sur les 7 derniers jours (lecture directe S3).

    Optimisé pour tenir < 5 s sur 0.5 vCPU / 1 Go : échantillon de stations,
    lecture des seules colonnes hour/fill_rate, concurrence bornée, cache 1 h.
    """
    global _PEAK_HOURS_CACHE, _PEAK_HOURS_CACHE_TIME
    now = datetime.now(timezone.utc)
    if (
        _PEAK_HOURS_CACHE is not None
        and _PEAK_HOURS_CACHE_TIME is not None
        and now - _PEAK_HOURS_CACHE_TIME < _PEAK_HOURS_TTL
    ):
        return _PEAK_HOURS_CACHE

    dates = [(now - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7)]

    ids = _list_station_ids()
    if not ids:
        return _PEAK_HOURS_CACHE or []
    # Échantillon réparti régulièrement sur la liste triée des station_id.
    if len(ids) > _PEAK_HOURS_SAMPLE:
        ids = sorted(ids)
        stride = len(ids) / _PEAK_HOURS_SAMPLE
        ids = [ids[int(i * stride)] for i in range(_PEAK_HOURS_SAMPLE)]

    keys = [
        f"status/station_id={sid}/date={d_str}/data.parquet"
        for d_str in dates
        for sid in ids
    ]

    df = _read_keys(keys, columns=["hour", "fill_rate", "timestamp"])
    if df.empty:
        return _PEAK_HOURS_CACHE or []

    if "hour" not in df.columns:
        df["hour"] = pd.to_datetime(df["timestamp"]).dt.hour

    grouped = df.groupby("hour")["fill_rate"].mean().reset_index().sort_values("hour")
    result = [
        {"hour": int(row["hour"]), "avg_fill_rate": round(float(row["fill_rate"]), 4)}
        for _, row in grouped.iterrows()
    ]

    _PEAK_HOURS_CACHE = result
    _PEAK_HOURS_CACHE_TIME = now
    return result


def get_heatmap_s3() -> list[dict]:
    """Calcule le fill_rate moyen par station aujourd'hui en lisant directement S3 sans Athena."""
    df = _read_today_status()
    if df.empty:
        return []
        
    grouped = df.groupby(["station_id", "name", "lat", "lon"])["fill_rate"].mean().reset_index()
    return [
        {
            "station_id": str(row["station_id"]),
            "name": str(row["name"]),
            "lat": float(row["lat"]),
            "lon": float(row["lon"]),
            "avg_fill_rate": round(float(row["fill_rate"]), 4)
        }
        for _, row in grouped.iterrows()
    ]