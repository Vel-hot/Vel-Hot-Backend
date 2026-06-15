from datetime import datetime

from sqlalchemy import Column, DateTime, Float, Integer, String

from app.database import Base


class Utilisateur(Base):
    """Comptes utilisateurs — auth JWT."""
    __tablename__ = "utilisateurs"

    id              = Column(Integer, primary_key=True, index=True)
    nom             = Column(String, nullable=False)
    prenom          = Column(String, nullable=False)
    email           = Column(String, unique=True, nullable=False, index=True)
    hashed_password = Column(String, nullable=False)
    # Rôles : "admin" | "analyste" | "user"
    role            = Column(String, default="user", nullable=False)
    created_at      = Column(DateTime, default=datetime.utcnow)


class HistoriqueStation(Base):
    """Snapshot horaire de chaque station — inséré à chaque appel GET /stations.
    Permet d'avoir un historique court-terme sans requêter S3/Athena.
    """
    __tablename__ = "historique_stations"

    id                  = Column(Integer, primary_key=True, index=True)
    station_id          = Column(String, nullable=False, index=True)
    fill_rate           = Column(Float, nullable=False)
    num_bikes_available = Column(Integer, nullable=False)
    num_docks_available = Column(Integer, nullable=False)
    status              = Column(String, nullable=False)   # OPEN / CLOSED / RENT_ONLY / RETURN_ONLY
    timestamp           = Column(DateTime, nullable=False, index=True)
