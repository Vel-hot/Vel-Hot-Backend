"""Inférence ML — porté depuis velhot-api-dev (Lambda de l'équipe data).

Charge le modèle pickle depuis S3 (bucket models), construit les features
(lag 1, lag 12, lag 288 + météo) et prédit fill_rate à t+15/t+30/t+60.
"""
import io
import json
import pickle
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

_MODEL = None
_MODEL_KEY = None


def _get_s3():
    return boto3.client("s3", region_name=settings.AWS_REGION)


def _get_model():
    """Charge (et met en cache) le modèle pointé par latest_model.txt dans le bucket models."""
    global _MODEL, _MODEL_KEY
    try:
        s3 = _get_s3()
        pointer = s3.get_object(Bucket=settings.S3_BUCKET_MODELS, Key="latest_model.txt")["Body"].read().decode()
        if pointer == _MODEL_KEY and _MODEL is not None:
            return _MODEL
        body = s3.get_object(Bucket=settings.S3_BUCKET_MODELS, Key=pointer)["Body"].read()
        _MODEL = pickle.loads(body)
        _MODEL_KEY = pointer
        logger.info("Modèle ML chargé : %s", pointer)
        return _MODEL
    except NoCredentialsError as e:
        raise DataSourceUnavailable("S3", "Credentials AWS non configurés") from e
    except ClientError as e:
        logger.error("Erreur chargement modèle : %s", e)
        raise DataSourceUnavailable("S3", f"Impossible de charger le modèle : {e}") from e
    except BotoCoreError as e:
        raise DataSourceUnavailable("S3", "Connexion à S3 impossible") from e


def _read_station_status(station_id: str, date_str: str) -> pd.DataFrame:
    try:
        s3 = _get_s3()
        key = f"status/station_id={station_id}/date={date_str}/data.parquet"
        body = s3.get_object(Bucket=settings.S3_BUCKET_SILVER, Key=key)["Body"].read()
        return pq.read_table(io.BytesIO(body)).to_pandas()
    except ClientError as e:
        logger.warning("Lecture impossible pour station %s date %s : %s", station_id, date_str, e)
        return pd.DataFrame()
    except Exception as e:
        logger.warning("Fichier Parquet illisible pour station %s date %s : %s", station_id, date_str, e)
        return pd.DataFrame()


def _get_meteo() -> tuple[float, float]:
    """Lit le dernier fichier météo du bucket bronze. Valeurs par défaut si indisponible."""
    temp, precip = 15.0, 0.0
    try:
        s3 = _get_s3()
        bronze_bucket = settings.S3_BUCKET_SILVER.replace("silver", "bronze")
        resp = s3.list_objects_v2(Bucket=bronze_bucket, Prefix="meteo/")
        keys = sorted([o["Key"] for o in resp.get("Contents", [])], reverse=True)
        if keys:
            body = s3.get_object(Bucket=bronze_bucket, Key=keys[0])["Body"].read()
            meteo = json.loads(body)
            main = meteo.get("data", {}).get("main", {})
            temp = main.get("temp", 15.0)
    except Exception as e:
        logger.warning("Météo indisponible, valeurs par défaut utilisées : %s", e)
    return temp, precip


def get_ml_features(station_id: str) -> Optional[dict]:
    """Construit le vecteur de features pour une station (lag 1 / 12 / 288 + météo)."""
    now = datetime.now(timezone.utc)

    df_today = _read_station_status(station_id, now.strftime("%Y-%m-%d"))
    if df_today.empty:
        return None

    row_df = df_today[df_today["station_id"].astype(str) == str(station_id)].sort_values("timestamp").iloc[-1:].copy()
    if row_df.empty:
        return None

    current_ts = pd.to_datetime(row_df["timestamp"].values[0])
    if df_today["timestamp"].dt.tz is not None:
        if current_ts.tzinfo is None:
            current_ts = current_ts.tz_localize(timezone.utc)
        else:
            current_ts = current_ts.tz_convert(timezone.utc)
    else:
        if current_ts.tzinfo is not None:
            current_ts = current_ts.tz_localize(None)

    lag_1 = row_df["fill_rate"].values[0]

    # Lag 1 (~5 min avant)
    lag_1_df = df_today[
        (df_today["station_id"].astype(str) == str(station_id)) &
        (df_today["timestamp"] < current_ts - pd.Timedelta(minutes=3))
    ].sort_values("timestamp")
    if not lag_1_df.empty:
        lag_1 = lag_1_df.iloc[-1]["fill_rate"]

    # Lag 12 (~1h avant)
    lag_12 = lag_1
    lag_12_cutoff = current_ts - pd.Timedelta(hours=1, minutes=10)
    if pd.Timestamp(lag_12_cutoff).date() == now.date():
        lag_12_df = df_today[
            (df_today["station_id"].astype(str) == str(station_id)) &
            (df_today["timestamp"] <= lag_12_cutoff)
        ].sort_values("timestamp")
        if not lag_12_df.empty:
            lag_12 = lag_12_df.iloc[-1]["fill_rate"]
    else:
        yesterday = (now - timedelta(days=1)).strftime("%Y-%m-%d")
        df_yesterday = _read_station_status(station_id, yesterday)
        if not df_yesterday.empty:
            lag_12_df = df_yesterday[df_yesterday["station_id"].astype(str) == str(station_id)].sort_values("timestamp")
            if not lag_12_df.empty:
                lag_12 = lag_12_df.iloc[-1]["fill_rate"]

    # Lag 288 (~24h avant, même heure hier)
    lag_288 = lag_12
    lag_288_cutoff = current_ts - pd.Timedelta(hours=23, minutes=50)
    if pd.Timestamp(lag_288_cutoff).date() == now.date():
        lag_288_df = df_today[
            (df_today["station_id"].astype(str) == str(station_id)) &
            (df_today["timestamp"] <= lag_288_cutoff)
        ].sort_values("timestamp")
        if not lag_288_df.empty:
            lag_288 = lag_288_df.iloc[-1]["fill_rate"]
    else:
        yesterday = (now - timedelta(days=1)).strftime("%Y-%m-%d")
        df_yesterday = _read_station_status(station_id, yesterday)
        if not df_yesterday.empty:
            lag_288_df = df_yesterday[
                (df_yesterday["station_id"].astype(str) == str(station_id)) &
                (df_yesterday["timestamp"] <= lag_288_cutoff)
            ].sort_values("timestamp")
            if not lag_288_df.empty:
                lag_288 = lag_288_df.iloc[-1]["fill_rate"]

    temp, precip = _get_meteo()

    return {
        "fill_rate": float(row_df["fill_rate"].values[0]),
        "hour_sin":  float(row_df["hour_sin"].values[0]),
        "hour_cos":  float(row_df["hour_cos"].values[0]),
        "dow_sin":   float(row_df["dow_sin"].values[0]),
        "dow_cos":   float(row_df["dow_cos"].values[0]),
        "is_weekend": int(row_df["is_weekend"].values[0]),
        "temp": temp,
        "precip": precip,
        "lag_1": float(lag_1),
        "lag_12": float(lag_12),
        "lag_288": float(lag_288),
    }


def predict_for_station(station_id: str) -> Optional[dict]:
    """Retourne {"t15": ..., "t30": ..., "t60": ...} ou None si pas de données."""
    features = get_ml_features(station_id)
    if features is None:
        return None

    try:
        model = _get_model()
        X = pd.DataFrame([features])
        pred = model.predict(X)[0]
        return {
            "t15": round(float(pred[0]), 4),
            "t30": round(float(pred[1]), 4),
            "t60": round(float(pred[2]), 4),
        }
    except Exception as e:
        logger.warning("Inférence ML impossible (modèle absent ou erreur), retour de prédictions simulées : %s", e)
        fill_rate = features["fill_rate"]
        return {
            "t15": round(max(0.0, min(1.0, fill_rate + 0.02)), 4),
            "t30": round(max(0.0, min(1.0, fill_rate - 0.05)), 4),
            "t60": round(max(0.0, min(1.0, fill_rate - 0.10)), 4),
        }
