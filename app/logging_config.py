"""Configuration du logging — sortie JSON-friendly pour CloudWatch.

Usage :
    from app.logging_config import get_logger
    logger = get_logger(__name__)
    logger.info("Stations récupérées", extra={"count": len(stations)})
"""
import logging
import sys

from app.config import settings


def setup_logging() -> None:
    """À appeler une fois au démarrage de l'app (voir main.py)."""
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(settings.LOG_LEVEL)
    root.handlers = [handler]

    # Réduire le bruit des libs tierces
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("botocore").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
