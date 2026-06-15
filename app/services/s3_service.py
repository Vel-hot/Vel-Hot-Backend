import io
from typing import Optional

import boto3
import pandas as pd
from botocore.exceptions import BotoCoreError, ClientError, NoCredentialsError

from app.config import settings
from app.exceptions import DataSourceUnavailable
from app.logging_config import get_logger

logger = get_logger(__name__)


def _get_s3():
    return boto3.client("s3", region_name=settings.AWS_REGION)


def _read_latest_parquet(prefix: str) -> pd.DataFrame:
    """Lit le fichier Parquet le plus récent dans un préfixe S3.

    Lève DataSourceUnavailable si S3 est inaccessible (credentials manquants,
    bucket inexistant, problème réseau, etc.) — ne lève PAS d'erreur si le
    préfixe est simplement vide (retourne un DataFrame vide).
    """
    try:
        s3 = _get_s3()
        resp = s3.list_objects_v2(Bucket=settings.S3_BUCKET_SILVER, Prefix=prefix)
    except NoCredentialsError as e:
        logger.error("Credentials AWS manquants : %s", e)
        raise DataSourceUnavailable("S3", "Credentials AWS non configurés") from e
    except ClientError as e:
        logger.error("Erreur S3 (%s) : %s", prefix, e)
        raise DataSourceUnavailable("S3", f"Accès refusé ou bucket introuvable : {e}") from e
    except BotoCoreError as e:
        logger.error("Erreur réseau S3 : %s", e)
        raise DataSourceUnavailable("S3", "Connexion à S3 impossible") from e

    objects = resp.get("Contents", [])
    if not objects:
        logger.warning("Aucun fichier trouvé dans s3://%s/%s", settings.S3_BUCKET_SILVER, prefix)
        return pd.DataFrame()

    latest = max(objects, key=lambda o: o["LastModified"])
    try:
        obj = s3.get_object(Bucket=settings.S3_BUCKET_SILVER, Key=latest["Key"])
        return pd.read_parquet(io.BytesIO(obj["Body"].read()))
    except ClientError as e:
        logger.error("Erreur lecture %s : %s", latest["Key"], e)
        raise DataSourceUnavailable("S3", f"Impossible de lire {latest['Key']}") from e
    except Exception as e:
        logger.error("Erreur parsing Parquet %s : %s", latest["Key"], e)
        raise DataSourceUnavailable("S3", f"Fichier Parquet illisible : {latest['Key']}") from e


def get_all_stations() -> list[dict]:
    """Retourne toutes les stations du dernier snapshot silver/status/."""
    df = _read_latest_parquet("status/")
    if df.empty:
        return []
    df = df.sort_values("timestamp").groupby("station_id").last().reset_index()
    return df.to_dict(orient="records")


def get_station_by_id(station_id: str) -> Optional[dict]:
    """Retourne une station précise ou None si introuvable."""
    for s in get_all_stations():
        if str(s["station_id"]) == str(station_id):
            return s
    return None


def get_predictions(station_id: Optional[str] = None) -> list[dict]:
    """Lit les prédictions depuis silver/predictions/.
    Si station_id est fourni, filtre sur cette station.
    """
    df = _read_latest_parquet("predictions/")
    if df.empty:
        return []
    if station_id is not None:
        df = df[df["station_id"].astype(str) == str(station_id)]
    return df.to_dict(orient="records")


def get_alerts(threshold_empty: float = 0.1, threshold_full: float = 0.9) -> list[dict]:
    """Lit les prédictions et retourne les stations en alerte sur pred_t30."""
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



"""
def get_all_stations() -> list[dict]:
    return [
        {
            "station_id": "1", "name": "Bellecour", "lat": 45.757, "lon": 4.832,
            "capacity": 20, "num_bikes_available": 12, "num_docks_available": 8,
            "fill_rate": 0.6, "status": "OPEN", "hour": datetime.now().hour,
            "hour_sin": 0.5, "hour_cos": 0.5, "dow_sin": 0.3, "dow_cos": 0.7,
            "is_weekend": False, "timestamp": datetime.now().isoformat(),
        },
        {
            "station_id": "2", "name": "Perrache", "lat": 45.749, "lon": 4.826,
            "capacity": 15, "num_bikes_available": 3, "num_docks_available": 12,
            "fill_rate": 0.2, "status": "OPEN", "hour": datetime.now().hour,
            "hour_sin": 0.5, "hour_cos": 0.5, "dow_sin": 0.3, "dow_cos": 0.7,
            "is_weekend": False, "timestamp": datetime.now().isoformat(),
        },
    ]


def get_station_by_id(station_id: str) -> Optional[dict]:
    for s in get_all_stations():
        if s["station_id"] == str(station_id):
            return s
    return None


def get_predictions(station_id: Optional[str] = None) -> list[dict]:
    return [{"station_id": str(station_id), "pred_t15": 0.58, "pred_t30": 0.55, "pred_t60": 0.50}]


def get_alerts() -> list[dict]:
    return [
        {"station_id": "3", "type": "EMPTY", "horizon": "30min", "predicted_fill_rate": 0.04}
    ]
"""