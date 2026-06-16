from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth import TokenData, get_current_user
from app.config import settings
from app.database import get_db
from app.schemas import StationOut
from app.services import lambda_api_client, ml_service, s3_service
from app.services.historique_service import save_snapshot

router = APIRouter()


@router.get("", response_model=list[StationOut],
            summary="Toutes les stations du jour")
def list_stations(
    db: Session = Depends(get_db),
    _user: TokenData = Depends(get_current_user),
):
    """Retourne la dernière lecture de chaque station.

    Source des données pilotée par USE_LAMBDA_API dans .env :
    - False (défaut) : lecture directe S3 silver (app.services.s3_service)
    - True            : appel HTTP à velhot-api-dev (app.services.lambda_api_client)
    """
    if settings.USE_LAMBDA_API:
        stations = lambda_api_client.get_all_stations()
    else:
        stations = s3_service.get_all_stations()

    if not stations:
        return []
    save_snapshot(db, stations)
    return stations


@router.get("/{station_id}", response_model=StationOut,
            summary="Une station + ses prédictions ML")
def get_station(
    station_id: str,
    _user: TokenData = Depends(get_current_user),
):
    """Retourne les données d'une station et le bloc predictions {t15, t30, t60}."""
    if settings.USE_LAMBDA_API:
        station = lambda_api_client.get_station_by_id(station_id)
        if station is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Station {station_id} introuvable",
            )
        return station

    station = s3_service.get_station_by_id(station_id)
    if station is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Station {station_id} introuvable",
        )
    preds = ml_service.predict_for_station(station_id)
    if preds:
        station["predictions"] = preds
    return station