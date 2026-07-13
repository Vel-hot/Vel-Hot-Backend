from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.auth import TokenData, get_current_user
from app.config import settings
from app.schemas import Predictions
from app.services import lambda_api_client, ml_service

router = APIRouter()


class PredictOut(BaseModel):
    station_id: str
    predictions: Predictions


@router.get("", response_model=PredictOut,
            summary="Prédictions ML pour une station")
def get_predict(
    station_id: str,
    _user: TokenData = Depends(get_current_user),
):
    """Les prédictions à la volée ont été retirées du backend car elles seront fournies via la table gold."""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Les prédictions ne sont plus gérées par ce backend. Elles seront intégrées via la table gold."
    )