import json
from typing import Optional

import boto3
from botocore.exceptions import BotoCoreError, ClientError, NoCredentialsError

from app.config import settings
from app.exceptions import DataSourceUnavailable
from app.logging_config import get_logger

logger = get_logger(__name__)

LAMBDA_FUNCTION_NAME = "velhot-api-dev"


def _get_lambda_client():
    return boto3.client("lambda", region_name=settings.AWS_REGION)


def _invoke(route: str, query: Optional[dict] = None) -> dict:
    """Invoque velhot-api-dev en simulant un event API Gateway HTTP v2."""
    payload = {
        "rawPath": route,
        "requestContext": {"http": {"method": "GET"}},
        "queryStringParameters": query,
    }
    try:
        client = _get_lambda_client()
        response = client.invoke(
            FunctionName=LAMBDA_FUNCTION_NAME,
            InvocationType="RequestResponse",
            Payload=json.dumps(payload),
        )
    except NoCredentialsError as e:
        raise DataSourceUnavailable("LambdaAPI", "Credentials AWS non configurés") from e
    except ClientError as e:
        logger.error("Erreur invocation %s sur %s : %s", LAMBDA_FUNCTION_NAME, route, e)
        raise DataSourceUnavailable("LambdaAPI", f"Invocation impossible : {e}") from e
    except BotoCoreError as e:
        raise DataSourceUnavailable("LambdaAPI", "Connexion à Lambda impossible") from e

    if response.get("FunctionError"):
        raw = response["Payload"].read().decode()
        logger.error("Erreur dans %s : %s", LAMBDA_FUNCTION_NAME, raw)
        raise DataSourceUnavailable("LambdaAPI", f"Erreur d'exécution : {raw}")

    result = json.loads(response["Payload"].read())
    status_code = result.get("statusCode", 200)
    body_raw = result.get("body", "{}")
    body = json.loads(body_raw) if isinstance(body_raw, str) else body_raw

    if status_code == 404:
        raise DataSourceUnavailable("LambdaAPI", "404 — ressource introuvable")
    if status_code >= 400:
        raise DataSourceUnavailable("LambdaAPI", f"{route} a répondu {status_code} : {body}")

    return body


def get_all_stations() -> list[dict]:
    body = _invoke("/stations")
    return body.get("stations", [])


def get_station_by_id(station_id: str) -> Optional[dict]:
    try:
        return _invoke(f"/stations/{station_id}")
    except DataSourceUnavailable as e:
        if "404" in e.detail:
            return None
        raise


def get_predict(station_id: str) -> Optional[dict]:
    try:
        return _invoke("/predict", query={"station_id": station_id})
    except DataSourceUnavailable as e:
        if "404" in e.detail:
            return None
        raise


def get_alerts() -> list[dict]:
    body = _invoke("/alerts")
    return body.get("alerts", [])


def get_peak_hours() -> list[dict]:
    body = _invoke("/dashboard/peak-hours")
    return body.get("data", [])


def get_heatmap() -> list[dict]:
    body = _invoke("/dashboard/heatmap")
    return body.get("stations", [])