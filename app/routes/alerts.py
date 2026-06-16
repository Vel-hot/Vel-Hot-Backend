from fastapi import APIRouter, Depends

from app.auth import TokenData, get_current_user
from app.config import settings
from app.schemas import AlertsResponse
from app.services import lambda_api_client, s3_service

router = APIRouter()


@router.get("", response_model=AlertsResponse,
            summary="Stations en alerte (vide ou plein dans 30 min)")
def get_alerts(_user: TokenData = Depends(get_current_user)):
    """Retourne les stations dont pred_t30 < 0.10 (EMPTY) ou > 0.90 (FULL).

    Source pilotée par USE_LAMBDA_API dans .env (voir app/config.py).
    """
    if settings.USE_LAMBDA_API:
        alerts = lambda_api_client.get_alerts()
    else:
        alerts = s3_service.get_alerts()
    return {"alerts": alerts}