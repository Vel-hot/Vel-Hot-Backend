from fastapi import APIRouter, Depends

from app.auth import TokenData, require_role
from app.config import settings
from app.exceptions import DataSourceUnavailable
from app.logging_config import get_logger
from app.schemas import HeatmapPointOut, PeakHourOut
from app.services import athena_service, s3_service

router = APIRouter()
logger = get_logger(__name__)


@router.get("/peak-hours", response_model=list[PeakHourOut],
            summary="Fill-rate moyen par heure (7 derniers jours)")
def peak_hours(
    _user: TokenData = Depends(require_role("admin", "analyste")),
):
    """Réservé aux analystes et admins.

    Agrégat calculé côté Athena (déporté hors du conteneur). Repli automatique
    sur la lecture S3 directe si Athena est indisponible (ex. table pas encore
    provisionnée) afin de ne jamais renvoyer d'erreur à l'utilisateur.
    """
    try:
        return athena_service.get_peak_hours()
    except DataSourceUnavailable as e:
        logger.warning("peak-hours: Athena indisponible (%s), repli S3", e.detail)
        return s3_service.get_peak_hours_s3()


@router.get("/heatmap", response_model=list[HeatmapPointOut],
            summary="Fill-rate moyen par station aujourd'hui")
def heatmap(
    _user: TokenData = Depends(require_role("admin", "analyste")),
):
    """Réservé aux analystes et admins. Athena avec repli S3 (cf. peak-hours)."""
    try:
        return athena_service.get_heatmap()
    except DataSourceUnavailable as e:
        logger.warning("heatmap: Athena indisponible (%s), repli S3", e.detail)
        return s3_service.get_heatmap_s3()