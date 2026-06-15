from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.auth import TokenData, get_current_user
from app.schemas import Predictions
from app.services import s3_service

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
    """Retourne uniquement les prédictions fill_rate à +15, +30 et +60 min."""
    preds = s3_service.get_predictions(station_id)
    if not preds:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Aucune prédiction pour la station {station_id}",
        )
    p = preds[0]
    return {
        "station_id": str(station_id),
        "predictions": {
            "t15": round(float(p.get("pred_t15", p.get("t15", 0))), 4),
            "t30": round(float(p.get("pred_t30", p.get("t30", 0))), 4),
            "t60": round(float(p.get("pred_t60", p.get("t60", 0))), 4),
        },
    }
