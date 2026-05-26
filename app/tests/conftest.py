"""
conftest.py — données fictives pour les tests

Permet de tester toutes les routes sans avoir besoin
d'une vraie base de données.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from main import app
from app.database import Base, get_db_silver, get_db_gold
from app.models import Station, StatutStation, Prediction
from datetime import datetime

# Base SQLite en mémoire pour les tests (pas besoin de PostgreSQL)
SQLALCHEMY_TEST_URL = "sqlite:///./test.db"

engine_test = create_engine(SQLALCHEMY_TEST_URL, connect_args={"check_same_thread": False})
TestingSession = sessionmaker(bind=engine_test, autocommit=False, autoflush=False)


def override_get_db_silver():
    db = TestingSession()
    try:
        yield db
    finally:
        db.close()


def override_get_db_gold():
    db = TestingSession()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="session", autouse=True)
def setup_database():
    """Crée les tables et insère des données fictives avant les tests."""
    Base.metadata.create_all(bind=engine_test)

    db = TestingSession()

    # Stations fictives
    stations = [
        Station(id=1, nom="Bellecour",  commune="Lyon", latitude=45.7579, longitude=4.8320, capacite_totale=20, est_active=True),
        Station(id=2, nom="Perrache",   commune="Lyon", latitude=45.7493, longitude=4.8265, capacite_totale=16, est_active=True),
        Station(id=3, nom="Part-Dieu",  commune="Lyon", latitude=45.7606, longitude=4.8598, capacite_totale=24, est_active=True),
        Station(id=4, nom="Hôtel de Ville", commune="Lyon", latitude=45.7676, longitude=4.8344, capacite_totale=18, est_active=True),
    ]
    db.add_all(stations)

    # Statuts fictifs
    statuts = [
        StatutStation(station_id=1, velos_dispo=5,  places_dispo=15, taux_remplissage=25.0,  timestamp=datetime.utcnow()),
        StatutStation(station_id=2, velos_dispo=0,  places_dispo=16, taux_remplissage=0.0,   timestamp=datetime.utcnow()),
        StatutStation(station_id=3, velos_dispo=20, places_dispo=4,  taux_remplissage=83.3,  timestamp=datetime.utcnow()),
        StatutStation(station_id=4, velos_dispo=9,  places_dispo=9,  taux_remplissage=50.0,  timestamp=datetime.utcnow()),
    ]
    db.add_all(statuts)

    # Prédictions fictives
    predictions = [
        Prediction(station_id=1, t_plus_15=30.0, t_plus_30=35.0, t_plus_60=40.0, confiance=0.85, timestamp=datetime.utcnow()),
        Prediction(station_id=3, t_plus_15=92.0, t_plus_30=95.0, t_plus_60=98.0, confiance=0.78, timestamp=datetime.utcnow()),
    ]
    db.add_all(predictions)

    db.commit()
    db.close()

    yield

    Base.metadata.drop_all(bind=engine_test)


@pytest.fixture
def client():
    """Client de test FastAPI avec les dépendances DB remplacées par SQLite."""
    app.dependency_overrides[get_db_silver] = override_get_db_silver
    app.dependency_overrides[get_db_gold]   = override_get_db_gold
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
