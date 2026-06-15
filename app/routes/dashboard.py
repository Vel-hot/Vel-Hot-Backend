from fastapi import APIRouter, Depends

from app.auth import TokenData, require_role
from app.schemas import HeatmapPointOut, PeakHourOut
from app.services import athena_service

router = APIRouter()


@router.get("/peak-hours", response_model=list[PeakHourOut],
            summary="Fill-rate moyen par heure (7 derniers jours)")
def peak_hours(
    _user: TokenData = Depends(require_role("admin", "analyste")),
):
    """Requête Athena — réservé aux analystes et admins."""
    return athena_service.get_peak_hours()


@router.get("/heatmap", response_model=list[HeatmapPointOut],
            summary="Fill-rate moyen par station aujourd'hui")
def heatmap(
    _user: TokenData = Depends(require_role("admin", "analyste")),
):
    """Requête Athena — réservé aux analystes et admins."""
    return athena_service.get_heatmap()
