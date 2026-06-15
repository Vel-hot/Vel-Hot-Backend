from fastapi import APIRouter, Depends

from app.auth import TokenData, get_current_user
from app.schemas import AlertsResponse
from app.services import s3_service

router = APIRouter()


@router.get("", response_model=AlertsResponse,
            summary="Stations en alerte (vide ou plein dans 30 min)")
def get_alerts(_user: TokenData = Depends(get_current_user)):
    """Lit les prédictions depuis S3 et retourne les stations dont
    pred_t30 < 0.10 (EMPTY) ou pred_t30 > 0.90 (FULL).
    """
    alerts = s3_service.get_alerts()
    return {"alerts": alerts}
