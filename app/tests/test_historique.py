"""Tests pour /historique/{station_id}."""
from datetime import datetime, timedelta

from app.models import HistoriqueStation


def test_historique_empty(client, auth_headers):
    resp = client.get("/historique/1", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json() == []


def test_historique_returns_records(client, auth_headers, db_session):
    now = datetime.utcnow()
    db_session.add_all([
        HistoriqueStation(station_id="1", fill_rate=0.5, num_bikes_available=10,
                          num_docks_available=10, status="OPEN", timestamp=now - timedelta(hours=2)),
        HistoriqueStation(station_id="1", fill_rate=0.6, num_bikes_available=12,
                          num_docks_available=8, status="OPEN", timestamp=now - timedelta(hours=1)),
        HistoriqueStation(station_id="2", fill_rate=0.3, num_bikes_available=3,
                          num_docks_available=12, status="OPEN", timestamp=now),
    ])
    db_session.commit()

    resp = client.get("/historique/1", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    assert all(d["station_id"] == "1" for d in data)
    # Tri décroissant par timestamp
    assert data[0]["fill_rate"] == 0.6


def test_historique_filter_by_date(client, auth_headers, db_session):
    now = datetime.utcnow()
    db_session.add_all([
        HistoriqueStation(station_id="1", fill_rate=0.5, num_bikes_available=10,
                          num_docks_available=10, status="OPEN", timestamp=now - timedelta(days=2)),
        HistoriqueStation(station_id="1", fill_rate=0.6, num_bikes_available=12,
                          num_docks_available=8, status="OPEN", timestamp=now),
    ])
    db_session.commit()

    from_date = (now - timedelta(days=1)).isoformat()
    resp = client.get(f"/historique/1?from={from_date}", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["fill_rate"] == 0.6
