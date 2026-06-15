from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth import TokenData, get_current_user
from app.database import get_db
from app.models import HistoriqueStation
from app.schemas import HistoriqueOut

router = APIRouter()


@router.get("/{station_id}", response_model=list[HistoriqueOut],
            summary="Historique d'une station depuis Aurora")
def get_historique(
    station_id: str,
    from_dt: Optional[datetime] = Query(None, alias="from", description="Date de début ISO 8601"),
    to_dt: Optional[datetime]   = Query(None, alias="to", description="Date de fin ISO 8601"),
    limit: int                  = Query(100, le=1000),
    db: Session                 = Depends(get_db),
    _user: TokenData            = Depends(get_current_user),
):
    """Retourne l'historique stocké dans Aurora PostgreSQL.
    Filtrable par plage de dates (?from=...&to=...).
    """
    q = db.query(HistoriqueStation).filter(HistoriqueStation.station_id == station_id)
    if from_dt:
        q = q.filter(HistoriqueStation.timestamp >= from_dt)
    if to_dt:
        q = q.filter(HistoriqueStation.timestamp <= to_dt)
    return q.order_by(HistoriqueStation.timestamp.desc()).limit(limit).all()
