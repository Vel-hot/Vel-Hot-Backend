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


def _read_parquet(key: str) -> pd.DataFrame:
    try:
        s3 = _get_s3()
        body = s3.get_object(Bucket=settings.S3_BUCKET_SILVER, Key=key)["Body"].read()
        return pq.read_table(io.BytesIO(body)).to_pandas()
    except ClientError as e:
        logger.warning("Lecture impossible %s : %s", key, e)
        return pd.DataFrame()
    except Exception as e:
        logger.warning("Fichier Parquet illisible %s : %s", key, e)
        return pd.DataFrame()


from concurrent.futures import ThreadPoolExecutor


def _read_status_for_date(date_str: str) -> pd.DataFrame:
    """Lit tous les fichiers status/station_id=*/date={date_str}/data.parquet."""
    objects = _list_objects("status/")
    keys = [o["Key"] for o in objects if f"date={date_str}" in o["Key"]]
    
    with ThreadPoolExecutor(max_workers=100) as executor:
        dfs = list(executor.map(_read_parquet, keys))
        
    dfs = [d for d in dfs if not d.empty]
    return pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()


def _read_today_status() -> pd.DataFrame:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    df = _read_status_for_date(today)
    if df.empty:
        logger.warning("Aucune donnée status pour %s dans s3://%s/status/", today, settings.S3_BUCKET_SILVER)
    return df


def _read_predictions_for_date(date_str: str) -> pd.DataFrame:
    """Lit tous les fichiers predictions/.../date={date_str}/..."""
    objects = _list_objects("predictions/")
    keys = [o["Key"] for o in objects if f"date={date_str}" in o["Key"]]
    
    with ThreadPoolExecutor(max_workers=100) as executor:
        dfs = list(executor.map(_read_parquet, keys))
        
    dfs = [d for d in dfs if not d.empty]
    return pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()


def _read_today_predictions() -> pd.DataFrame:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    df = _read_predictions_for_date(today)
    if df.empty:
        logger.warning("Aucune prédiction pour %s dans s3://%s/predictions/", today, settings.S3_BUCKET_SILVER)
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


def get_latest_pull_time(dt: datetime) -> datetime:
    """Calcule le dernier moment attendu de mise à jour de l'API (XX:33 pour laisser 3 min de marge)."""
    pull_time = dt.replace(minute=33, second=0, microsecond=0)
    if dt.minute < 33:
        pull_time -= timedelta(hours=1)
    return pull_time


def get_all_stations() -> list[dict]:
    """Toutes les stations — dernière lecture du jour par station_id, avec cache intelligent basé sur l'heure du pull."""
    global _STATIONS_CACHE, _STATIONS_CACHE_TIME
    
    now = datetime.now(timezone.utc)
    if _STATIONS_CACHE is not None and _STATIONS_CACHE_TIME is not None:
        last_pull = get_latest_pull_time(now)
        if _STATIONS_CACHE_TIME >= last_pull:
            logger.info("Retour des stations depuis le cache in-memory (valide, dernier pull attendu à %s)", last_pull.strftime("%H:%M"))
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


def get_station_by_id(station_id: str) -> Optional[dict]:
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