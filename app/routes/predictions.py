"""Prédictions ML servies depuis la table gold (silver/predictions/).

La couche gold est produite par la Lambda velhot-predict-dev toutes les 15 min
à partir du dernier modèle entraîné. Le backend se contente de la lire et de
l'exposer (fill_rate prédit + nombre de vélos dérivé) — plus d'inférence à la volée.
"""
from fastapi import APIRouter, Depends, HTTPException, status

from app.auth import TokenData, get_current_user
from app.schemas import Predictions, PredictionsResponse, StationPredictionOut
from app.services import s3_service

router = APIRouter()


def _f(value, default=0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _opt_str(value):
    return None if value is None else str(value)


def _map_record(rec: dict) -> StationPredictionOut:
    """Mappe une ligne de la table gold vers le schéma d'API."""
    capacity = int(_f(rec.get("capacity"), 0))
    t15 = _f(rec.get("pred_t15"))
    t30 = _f(rec.get("pred_t30"))
    t60 = _f(rec.get("pred_t60"))

    def bikes(fill_rate: float) -> float:
        return round(max(0.0, min(1.0, fill_rate)) * capacity)

    return StationPredictionOut(
        station_id=str(rec.get("station_id")),
        name=str(rec.get("name", "")),
        lat=_f(rec.get("lat")),
        lon=_f(rec.get("lon")),
        capacity=capacity,
        current_fill_rate=_f(rec.get("current_fill_rate")),
        fill_rate=Predictions(t15=round(t15, 4), t30=round(t30, 4), t60=round(t60, 4)),
        bikes=Predictions(t15=bikes(t15), t30=bikes(t30), t60=bikes(t60)),
        source_timestamp=_opt_str(rec.get("source_timestamp")),
        prediction_ts=_opt_str(rec.get("prediction_ts")),
    )


@router.get("", response_model=PredictionsResponse,
            summary="Prédictions ML (table gold) pour toutes les stations")
def list_predictions(_user: TokenData = Depends(get_current_user)):
    """Dernières prédictions pré-calculées pour l'ensemble des stations."""
    records = s3_service.get_predictions()
    predictions = [_map_record(r) for r in records]
    generated_at = _opt_str(records[0].get("prediction_ts")) if records else None
    model_key = _opt_str(records[0].get("model_key")) if records else None
    return PredictionsResponse(
        generated_at=generated_at,
        model_key=model_key,
        count=len(predictions),
        predictions=predictions,
    )


@router.get("/{station_id}", response_model=StationPredictionOut,
            summary="Prédictions ML (table gold) pour une station")
def get_predict(
    station_id: str,
    _user: TokenData = Depends(get_current_user),
):
    records = s3_service.get_predictions(station_id)
    if not records:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Aucune prédiction disponible pour la station {station_id}",
        )
    return _map_record(records[0])
