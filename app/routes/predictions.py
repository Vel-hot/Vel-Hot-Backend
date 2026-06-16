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
    """Calcule le fill_rate prédit à +15, +30 et +60 min.

    Source pilotée par USE_LAMBDA_API dans .env (voir app/config.py).
    """
    if settings.USE_LAMBDA_API:
        result = lambda_api_client.get_predict(station_id)
        if result is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Aucune donnée disponible pour la station {station_id}",
            )
        return result

    preds = ml_service.predict_for_station(station_id)
    if preds is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Aucune donnée disponible pour la station {station_id}",
        )
    return {"station_id": str(station_id), "predictions": preds}