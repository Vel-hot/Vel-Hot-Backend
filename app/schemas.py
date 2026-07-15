from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, EmailStr


# ── Auth ──────────────────────────────────────────────────────────────────────

class RegisterIn(BaseModel):
    nom: str
    prenom: str
    email: EmailStr
    password: str


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: int
    nom: str
    prenom: str
    email: str
    role: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Stations ──────────────────────────────────────────────────────────────────

class Predictions(BaseModel):
    t15: float
    t30: float
    t60: float


class StationPredictionOut(BaseModel):
    """Prédiction gold pour une station (fill_rate prédit + vélos dérivés)."""
    station_id: str
    name: str
    lat: float
    lon: float
    capacity: int
    current_fill_rate: float
    # fill_rate prédit (0..1) aux horizons +15 / +30 / +60 min
    fill_rate: Predictions
    # nombre de vélos prédit = round(fill_rate * capacity)
    bikes: Predictions
    source_timestamp: Optional[str] = None
    prediction_ts: Optional[str] = None


class PredictionsResponse(BaseModel):
    generated_at: Optional[str] = None
    model_key: Optional[str] = None
    count: int
    predictions: List[StationPredictionOut]


class StationOut(BaseModel):
    station_id: str
    name: str
    lat: float
    lon: float
    capacity: int
    num_bikes_available: int
    num_docks_available: int
    fill_rate: float
    status: str
    hour: int
    hour_sin: float
    hour_cos: float
    dow_sin: float
    dow_cos: float
    is_weekend: bool
    timestamp: str
    predictions: Optional[Predictions] = None


# ── Alerts ────────────────────────────────────────────────────────────────────

class AlertOut(BaseModel):
    station_id: str
    type: str           # "EMPTY" | "FULL"
    horizon: str        # "30min"
    predicted_fill_rate: float


class AlertsResponse(BaseModel):
    alerts: List[AlertOut]


# ── Dashboard ─────────────────────────────────────────────────────────────────

class PeakHourOut(BaseModel):
    hour: int
    avg_fill_rate: float


class HeatmapPointOut(BaseModel):
    station_id: str
    name: str
    lat: float
    lon: float
    avg_fill_rate: float


# ── Historique ────────────────────────────────────────────────────────────────

class HistoriqueOut(BaseModel):
    station_id: str
    fill_rate: float
    num_bikes_available: int
    num_docks_available: int
    status: str
    timestamp: datetime

    model_config = {"from_attributes": True}
