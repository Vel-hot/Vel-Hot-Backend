from pydantic import BaseModel, Field, EmailStr
from datetime import datetime
from typing import Optional


# 
#  Stations
# 

class StationBase(BaseModel):
    id:              int
    nom:             str
    commune:         str
    adresse:         Optional[str] = None
    latitude:        float
    longitude:       float
    capacite_totale: int


class StatutBase(BaseModel):
    velos_dispo:       int
    places_dispo:      int
    velos_mecaniques:  Optional[int] = 0
    velos_electriques: Optional[int] = 0
    taux_remplissage:  float = Field(..., ge=0, le=100)
    timestamp:         Optional[datetime] = None

    model_config = {"from_attributes": True}


class StationAvecStatut(StationBase):
    """Une station avec son statut temps réel — utilisée par GET /stations."""
    statut: Optional[StatutBase] = None
    etat:   str = Field(description="'disponible' | 'presque_vide' | 'vide' | 'presque_pleine' | 'pleine'")

    class Config:
        from_attributes = True


# 
#  Prédictions
#

class PredictionSchema(BaseModel):
    """Prédictions du modèle ML pour une station."""
    station_id:  int
    taux_actuel: float = Field(..., description="Taux de remplissage actuel")
    t_plus_15:   Optional[float] = Field(None, description="Taux prédit dans 15 min")
    t_plus_30:   Optional[float] = Field(None, description="Taux prédit dans 30 min")
    t_plus_60:   Optional[float] = Field(None, description="Taux prédit dans 60 min")
    confiance:   Optional[float] = Field(None, description="Score de confiance 0.0 à 1.0")
    timestamp:   datetime
    alerte:      Optional[str]   = Field(None, description="Message d'alerte si saturation imminente")

    class Config:
        from_attributes = True


# 
#  Alternatives
# 

class StationAlternative(StationBase):
    """Une station alternative avec sa distance et son statut."""
    distance_metres: float = Field(..., description="Distance en mètres depuis la station d'origine")
    velos_dispo:     int
    places_dispo:    int
    taux_remplissage: float

    class Config:
        from_attributes = True


#
#  Alertes
# 

class AlerteSchema(BaseModel):
    """Une alerte active sur le réseau."""
    id:                int
    station_id:        int
    station_nom:       str
    type_alerte:       str  = Field(..., description="'pleine' ou 'vide'")
    minutes_restantes: int
    timestamp:         datetime

    class Config:
        from_attributes = True


class AbonnementCreate(BaseModel):
    """Corps de la requête pour s'abonner aux alertes d'une station."""
    station_id: int
    email:      Optional[EmailStr] = None


class AbonnementResponse(BaseModel):
    message:    str
    station_id: int
    token:      str


# 
#  Analytics
# 

class TopStation(BaseModel):
    """Une station du top des plus utilisées."""
    station_id:   int
    station_nom:  str
    commune:      str
    nb_rotations: int   # nombre de vélos pris/déposés sur la période


class TendanceHeure(BaseModel):
    """Utilisation moyenne pour une heure donnée."""
    heure:              int   = Field(..., ge=0, le=23)
    taux_moyen:         float
    jour_de_semaine:    str   # "lundi", "mardi", etc.


class HeatmapPoint(BaseModel):
    """Un point de la carte thermique."""
    latitude:  float
    longitude: float
    intensite: float = Field(..., ge=0, le=1, description="Intensité normalisée 0-1")
