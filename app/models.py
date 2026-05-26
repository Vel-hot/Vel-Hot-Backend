from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base
from sqlalchemy import Column, Integer, Float, String, DateTime, Boolean, ForeignKey, func


#  Base velohot_silver (données temps réel)

class Station(Base):
    """
    Informations fixes d'une station Vélo'v.
    Cette table est remplie une fois et rarement modifiée.
    """
    __tablename__ = "stations"

    id               = Column(Integer, primary_key=True, index=True)
    nom              = Column(String, nullable=False)
    commune          = Column(String, nullable=False)
    adresse          = Column(String, nullable=True)
    latitude         = Column(Float, nullable=False)
    longitude        = Column(Float, nullable=False)
    capacite_totale  = Column(Integer, nullable=False)
    est_active       = Column(Boolean, default=True)

    # Relation vers les statuts temps réel
    statuts = relationship("StatutStation", back_populates="station")

    def __repr__(self):
        return f"<Station id={self.id} nom={self.nom}>"


class StatutStation(Base):
    """
    Statut d'une station à un instant T.
    Mis à jour toutes les 5 minutes par la Lambda d'ingestion.
    """
    __tablename__ = "statut_stations"

    id               = Column(Integer, primary_key=True, index=True)
    station_id       = Column(Integer, ForeignKey("stations.id"), nullable=False, index=True)
    velos_dispo      = Column(Integer, nullable=False)
    places_dispo     = Column(Integer, nullable=False)
    velos_mecaniques = Column(Integer, default=0)
    velos_electriques= Column(Integer, default=0)
    taux_remplissage = Column(Float, nullable=False)  # 0.0 à 100.0
    timestamp = Column(DateTime, default=datetime.utcnow, server_default=func.now(), index=True)

    station = relationship("Station", back_populates="statuts")

    def __repr__(self):
        return f"<Statut station_id={self.station_id} taux={self.taux_remplissage}%>"


class Alerte(Base):
    """
    Alerte générée quand une station va être pleine ou vide dans moins de 30 min.
    """
    __tablename__ = "alertes"

    id                = Column(Integer, primary_key=True, index=True)
    station_id        = Column(Integer, ForeignKey("stations.id"), nullable=False, index=True)
    type_alerte       = Column(String, nullable=False)  # "pleine" ou "vide"
    minutes_restantes = Column(Integer, nullable=False)
    active            = Column(Boolean, default=True)
    timestamp         = Column(DateTime, default=datetime.utcnow, index=True)

    def __repr__(self):
        return f"<Alerte station_id={self.station_id} type={self.type_alerte}>"


class AbonnementAlerte(Base):
    """
    Abonnement d'un utilisateur aux alertes d'une station.
    """
    __tablename__ = "abonnements_alertes"

    id         = Column(Integer, primary_key=True, index=True)
    station_id = Column(Integer, ForeignKey("stations.id"), nullable=False, index=True)
    email      = Column(String, nullable=True)
    token      = Column(String, nullable=True)   # pour identifier l'utilisateur
    timestamp  = Column(DateTime, default=datetime.utcnow)


#
#  Base velohot_gold (prédictions ML)
# 

class Prediction(Base):
    """
    Prédictions du modèle LSTM pour une station.
    Remplie par l'équipe ML via SageMaker.
    """
    __tablename__ = "predictions"

    id              = Column(Integer, primary_key=True, index=True)
    station_id      = Column(Integer, nullable=False, index=True)
    t_plus_15       = Column(Float, nullable=True)   # taux de remplissage dans 15 min
    t_plus_30       = Column(Float, nullable=True)   # taux de remplissage dans 30 min
    t_plus_60       = Column(Float, nullable=True)   # taux de remplissage dans 60 min
    confiance       = Column(Float, nullable=True)   # score de confiance 0.0 à 1.0
    timestamp       = Column(DateTime, default=datetime.utcnow, index=True)

    def __repr__(self):
        return f"<Prediction station_id={self.station_id} t+15={self.t_plus_15}%>"
