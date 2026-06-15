"""Insertion automatique dans historique_stations après chaque lecture S3."""
from datetime import datetime

from sqlalchemy.orm import Session

from app.logging_config import get_logger
from app.models import HistoriqueStation

logger = get_logger(__name__)


def save_snapshot(db: Session, stations: list[dict]) -> None:
    """Insère un snapshot de toutes les stations dans Aurora.

    N'interrompt jamais la réponse de l'API même en cas d'échec d'insertion.
    """
    try:
        records = [
            HistoriqueStation(
                station_id          = str(s["station_id"]),
                fill_rate           = float(s["fill_rate"]),
                num_bikes_available = int(s["num_bikes_available"]),
                num_docks_available = int(s["num_docks_available"]),
                status              = str(s.get("status", "UNKNOWN")),
                timestamp           = datetime.fromisoformat(s["timestamp"])
                                      if isinstance(s["timestamp"], str)
                                      else s["timestamp"],
            )
            for s in stations
        ]
        db.bulk_save_objects(records)
        db.commit()
        logger.debug("Snapshot historique inséré : %d stations", len(records))
    except Exception as e:
        db.rollback()
        logger.error("Erreur insertion historique : %s", e)