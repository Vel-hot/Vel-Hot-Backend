from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth import TokenData, get_current_user
from app.database import get_db
from app.schemas import StationOut
from app.services import s3_service
from app.services.historique_service import save_snapshot

router = APIRouter()


@router.get("", response_model=list[StationOut],
            summary="Toutes les stations du jour")
def list_stations(
    db: Session = Depends(get_db),
    _user: TokenData = Depends(get_current_user),
):
    """Retourne la dernière lecture de chaque station depuis S3.
    Insère automatiquement un snapshot dans historique_stations.
    """
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
    station = s3_service.get_station_by_id(station_id)
    if station is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Station {station_id} introuvable",
        )

    preds = s3_service.get_predictions(station_id)
    if preds:
        p = preds[0]
        station["predictions"] = {
            "t15": round(float(p.get("pred_t15", p.get("t15", 0))), 4),
            "t30": round(float(p.get("pred_t30", p.get("t30", 0))), 4),
            "t60": round(float(p.get("pred_t60", p.get("t60", 0))), 4),
        }
    return station
