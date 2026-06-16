from fastapi import APIRouter, Depends

from app.auth import TokenData, require_role
from app.config import settings
from app.schemas import HeatmapPointOut, PeakHourOut
from app.services import athena_service, lambda_api_client

router = APIRouter()


@router.get("/peak-hours", response_model=list[PeakHourOut],
            summary="Fill-rate moyen par heure (7 derniers jours)")
def peak_hours(
    _user: TokenData = Depends(require_role("admin", "analyste")),
):
    """Réservé aux analystes et admins.

    Source pilotée par USE_LAMBDA_API dans .env (voir app/config.py).
    """
    if settings.USE_LAMBDA_API:
        return lambda_api_client.get_peak_hours()
    return athena_service.get_peak_hours()


@router.get("/heatmap", response_model=list[HeatmapPointOut],
            summary="Fill-rate moyen par station aujourd'hui")
def heatmap(
    _user: TokenData = Depends(require_role("admin", "analyste")),
):
    """Réservé aux analystes et admins.

    Source pilotée par USE_LAMBDA_API dans .env (voir app/config.py).
    """
    if settings.USE_LAMBDA_API:
        return lambda_api_client.get_heatmap()
    return athena_service.get_heatmap()