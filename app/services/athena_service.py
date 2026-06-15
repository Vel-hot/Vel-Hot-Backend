"""Requêtes Athena pour les endpoints /dashboard."""
import time

import boto3
import pandas as pd
from botocore.exceptions import BotoCoreError, ClientError, NoCredentialsError

from app.config import settings
from app.exceptions import DataSourceUnavailable
from app.logging_config import get_logger

logger = get_logger(__name__)

POLL_INTERVAL = 1
MAX_WAIT      = 30


def _run_query(sql: str) -> pd.DataFrame:
    try:
        client = boto3.client("athena", region_name=settings.AWS_REGION)
        response = client.start_query_execution(
            QueryString=sql,
            QueryExecutionContext={"Database": settings.ATHENA_DATABASE},
            ResultConfiguration={"OutputLocation": settings.ATHENA_OUTPUT_BUCKET},
        )
    except NoCredentialsError as e:
        logger.error("Credentials AWS manquants pour Athena : %s", e)
        raise DataSourceUnavailable("Athena", "Credentials AWS non configurés") from e
    except ClientError as e:
        logger.error("Erreur démarrage requête Athena : %s", e)
        raise DataSourceUnavailable("Athena", f"Impossible de lancer la requête : {e}") from e
    except BotoCoreError as e:
        logger.error("Erreur réseau Athena : %s", e)
        raise DataSourceUnavailable("Athena", "Connexion à Athena impossible") from e

    execution_id = response["QueryExecutionId"]

    elapsed = 0
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
        logger.error("Timeout Athena après %ss", MAX_WAIT)
        raise DataSourceUnavailable("Athena", f"Timeout après {MAX_WAIT}s")

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
    sql = """
        SELECT
            CAST(hour AS INTEGER)       AS hour,
            ROUND(AVG(fill_rate), 4)    AS avg_fill_rate
        FROM status
        WHERE timestamp >= DATE_ADD('day', -7, CURRENT_DATE)
        GROUP BY hour
        ORDER BY hour
    """
    df = _run_query(sql)
    if df.empty:
        return []
    df["hour"]          = df["hour"].astype(int)
    df["avg_fill_rate"] = df["avg_fill_rate"].astype(float)
    return df.to_dict(orient="records")


def get_heatmap() -> list[dict]:
    """Fill_rate moyen par station aujourd'hui avec lat/lon."""
    sql = """
        SELECT
            station_id,
            ANY_VALUE(name)             AS name,
            ANY_VALUE(lat)              AS lat,
            ANY_VALUE(lon)              AS lon,
            ROUND(AVG(fill_rate), 4)    AS avg_fill_rate
        FROM status
        WHERE timestamp >= CURRENT_DATE
        GROUP BY station_id
    """
    df = _run_query(sql)
    if df.empty:
        return []
    df["lat"]           = df["lat"].astype(float)
    df["lon"]           = df["lon"].astype(float)
    df["avg_fill_rate"] = df["avg_fill_rate"].astype(float)
    return df.to_dict(orient="records")