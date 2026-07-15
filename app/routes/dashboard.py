from fastapi import APIRouter, Depends

from app.auth import TokenData, require_role
from app.config import settings
from app.schemas import HeatmapPointOut, PeakHourOut
from app.services import s3_service

router = APIRouter()


@router.get("/peak-hours", response_model=list[PeakHourOut],
            summary="Fill-rate moyen par heure (7 derniers jours)")
def peak_hours(
    _user: TokenData = Depends(require_role("admin", "analyste")),
):
    """Réservé aux analystes et admins. (Lit directement S3 sans Athena)"""
    return s3_service.get_peak_hours_s3()


@router.get("/heatmap", response_model=list[HeatmapPointOut],
            summary="Fill-rate moyen par station aujourd'hui")
def heatmap(
    _user: TokenData = Depends(require_role("admin", "analyste")),
):
    """Réservé aux analystes et admins. (Lit directement S3 sans Athena)"""
    return s3_service.get_heatmap_s3()