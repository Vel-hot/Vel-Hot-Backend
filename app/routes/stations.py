from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.auth import TokenData, get_current_user
from app.config import settings
from app.database import get_db
from app.schemas import StationOut
from app.services import lambda_api_client, ml_service, s3_service
from app.services.historique_service import save_snapshot

router = APIRouter()


@router.get("/snapshot", response_model=list[StationOut],
            summary="État de toutes les stations à un instant donné")
def stations_snapshot(
    at: datetime = Query(..., description="Instant ISO 8601 (ex. 2026-07-15T14:30:00Z)"),
    _user: TokenData = Depends(get_current_user),
):
    """Alimente le slider temporel : dernier relevé <= `at` pour chaque station.

    Lecture directe du silver S3 (le mode Lambda API n'expose pas l'historique
    intra-journalier). Renvoie [] si `at` précède le premier relevé du jour.
    """
    return s3_service.get_stations_snapshot(at)


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
            summary="Une station (sans prédictions)")
def get_station(
    station_id: str,
    _user: TokenData = Depends(get_current_user),
):
    """Retourne les données d'une station (les prédictions ne sont plus gérées par ce backend)."""
    if settings.USE_LAMBDA_API:
        station = lambda_api_client.get_station_by_id(station_id)
        if station is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Station {station_id} introuvable",
            )
        if isinstance(station, dict) and "predictions" in station:
            station["predictions"] = None
        return station

    station = s3_service.get_station_by_id(station_id)
    if station is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Station {station_id} introuvable",
        )
    station["predictions"] = None
    return station