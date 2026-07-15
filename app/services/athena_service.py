"""Requêtes Athena pour /dashboard/peak-hours et /dashboard/heatmap.

Adapté au schéma réel (base velhot_silver_dev, table `status_pp`, colonne de
partition `date` au format YYYY-MM-DD, workgroup velhot-dev).

`status_pp` est une table en *partition projection* (définie côté Terraform)
qui expose `station_id` UNIQUEMENT en clé de partition — contrairement à la
table `status` produite par le crawler, invalide car `station_id` y est à la
fois colonne de données et partition (HIVE_INVALID_METADATA: duplicate columns).
"""
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

import boto3
import pandas as pd
from botocore.exceptions import BotoCoreError, ClientError, NoCredentialsError

from app.config import settings
from app.exceptions import DataSourceUnavailable
from app.logging_config import get_logger

logger = get_logger(__name__)

POLL_INTERVAL = 0.5
MAX_WAIT      = 15

# Table Athena en partition projection (voir Terraform aws_glue_catalog_table).
_TABLE = "status_pp"

# Caches résultats : ces agrégats évoluent lentement. Le cache garantit des
# réponses < 5 s (souvent quelques ms) même si une requête Athena froide prend
# 2-4 s, et limite le coût (octets scannés facturés).
_PEAK_CACHE: Optional[list[dict]] = None
_PEAK_CACHE_TIME: Optional[datetime] = None
_PEAK_TTL = timedelta(hours=1)

_HEATMAP_CACHE: Optional[list[dict]] = None
_HEATMAP_CACHE_TIME: Optional[datetime] = None
_HEATMAP_TTL = timedelta(minutes=5)


def _run_query(sql: str) -> pd.DataFrame:
    try:
        client = boto3.client("athena", region_name=settings.AWS_REGION)
        response = client.start_query_execution(
            QueryString=sql,
            QueryExecutionContext={"Database": settings.ATHENA_DATABASE},
            ResultConfiguration={"OutputLocation": settings.ATHENA_OUTPUT_BUCKET},
            WorkGroup=settings.ATHENA_WORKGROUP,
        )
    except NoCredentialsError as e:
        raise DataSourceUnavailable("Athena", "Credentials AWS non configurés") from e
    except ClientError as e:
        logger.error("Erreur démarrage requête Athena : %s", e)
        raise DataSourceUnavailable("Athena", f"Impossible de lancer la requête : {e}") from e
    except BotoCoreError as e:
        raise DataSourceUnavailable("Athena", "Connexion à Athena impossible") from e

    execution_id = response["QueryExecutionId"]

    elapsed = 0
    state = None
    while elapsed < MAX_WAIT:
        time.sleep(POLL_INTERVAL)
        elapsed += POLL_INTERVAL
        try:
            status_resp = client.get_query_execution(QueryExecutionId=execution_id)
        except ClientError as e:
            raise DataSourceUnavailable("Athena", f"Erreur de suivi de requête : {e}") from e

        state = status_resp["QueryExecution"]["Status"]["State"]
        if state == "SUCCEEDED":
            break
        if state in ("FAILED", "CANCELLED"):
            reason = status_resp["QueryExecution"]["Status"].get("StateChangeReason", "")
            logger.error("Requête Athena %s : %s", state, reason)
            raise DataSourceUnavailable("Athena", f"Requête {state} : {reason}")
    else:
        raise DataSourceUnavailable("Athena", f"Timeout après {MAX_WAIT}s")

    if state != "SUCCEEDED":
        raise DataSourceUnavailable("Athena", f"Requête {state}")

    try:
        paginator = client.get_paginator("get_query_results")
        rows, columns = [], None
        for page in paginator.paginate(QueryExecutionId=execution_id):
            result = page["ResultSet"]
            if columns is None:
                columns = [c["Label"] for c in result["ResultSetMetadata"]["ColumnInfo"]]
            for row in result["Rows"][1:]:
                rows.append([d.get("VarCharValue", "") for d in row["Data"]])
    except ClientError as e:
        raise DataSourceUnavailable("Athena", f"Impossible de récupérer les résultats : {e}") from e

    return pd.DataFrame(rows, columns=columns) if rows else pd.DataFrame()


def get_peak_hours() -> list[dict]:
    """Fill_rate moyen par heure sur les 7 derniers jours."""
    global _PEAK_CACHE, _PEAK_CACHE_TIME
    now = datetime.now(timezone.utc)
    if (
        _PEAK_CACHE is not None
        and _PEAK_CACHE_TIME is not None
        and now - _PEAK_CACHE_TIME < _PEAK_TTL
    ):
        return _PEAK_CACHE

    sql = f"""
        SELECT hour, AVG(fill_rate) AS avg_fill_rate
        FROM {settings.ATHENA_DATABASE}.{_TABLE}
        WHERE date >= date_format(current_date - interval '7' day, '%Y-%m-%d')
        GROUP BY hour
        ORDER BY hour
    """
    df = _run_query(sql)
    if df.empty:
        return _PEAK_CACHE or []
    df["hour"]          = df["hour"].astype(int)
    df["avg_fill_rate"] = df["avg_fill_rate"].astype(float).round(4)
    result = df.to_dict(orient="records")
    _PEAK_CACHE, _PEAK_CACHE_TIME = result, now
    return result


def get_heatmap() -> list[dict]:
    """Fill_rate moyen par station aujourd'hui avec lat/lon."""
    global _HEATMAP_CACHE, _HEATMAP_CACHE_TIME
    now = datetime.now(timezone.utc)
    if (
        _HEATMAP_CACHE is not None
        and _HEATMAP_CACHE_TIME is not None
        and now - _HEATMAP_CACHE_TIME < _HEATMAP_TTL
    ):
        return _HEATMAP_CACHE

    # `date` est une partition string 'YYYY-MM-DD' : on compare à une chaîne,
    # pas au type DATE (current_date), sinon mismatch de types.
    sql = f"""
        SELECT
            station_id,
            ANY_VALUE(name) AS name,
            lat,
            lon,
            AVG(fill_rate) AS avg_fill_rate
        FROM {settings.ATHENA_DATABASE}.{_TABLE}
        WHERE date = date_format(current_date, '%Y-%m-%d')
        GROUP BY station_id, lat, lon
    """
    df = _run_query(sql)
    if df.empty:
        return _HEATMAP_CACHE or []
    df["lat"]           = df["lat"].astype(float)
    df["lon"]           = df["lon"].astype(float)
    df["avg_fill_rate"] = df["avg_fill_rate"].astype(float).round(4)
    result = df.to_dict(orient="records")
    _HEATMAP_CACHE, _HEATMAP_CACHE_TIME = result, now
    return result