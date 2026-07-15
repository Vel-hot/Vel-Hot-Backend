"""Tests pour /dashboard (rôles) et la gestion d'erreur DataSourceUnavailable."""
from unittest.mock import patch

from app.exceptions import DataSourceUnavailable

FAKE_PEAK_HOURS = [{"hour": 8, "avg_fill_rate": 0.42}, {"hour": 18, "avg_fill_rate": 0.71}]
FAKE_HEATMAP = [{"station_id": "1", "name": "Bellecour", "lat": 45.757, "lon": 4.832, "avg_fill_rate": 0.55}]


@patch("app.routes.dashboard.s3_service.get_peak_hours_s3", return_value=FAKE_PEAK_HOURS)
def test_dashboard_allowed_for_user(mock_s3, client, auth_headers):
    """Tous les utilisateurs (y compris 'user') peuvent accéder au dashboard."""
    resp = client.get("/api/dashboard/peak-hours", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    assert data[0]["hour"] == 8


@patch("app.routes.dashboard.s3_service.get_peak_hours_s3", return_value=FAKE_PEAK_HOURS)
def test_dashboard_peak_hours_as_admin(mock_s3, client, admin_headers):
    resp = client.get("/api/dashboard/peak-hours", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    assert data[0]["hour"] == 8


@patch("app.routes.dashboard.s3_service.get_heatmap_s3", return_value=FAKE_HEATMAP)
def test_dashboard_heatmap_as_admin(mock_s3, client, admin_headers):
    resp = client.get("/api/dashboard/heatmap", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data[0]["station_id"] == "1"


@patch("app.routes.dashboard.s3_service.get_peak_hours_s3",
       side_effect=DataSourceUnavailable("S3", "Credentials AWS non configurés"))
def test_dashboard_returns_503_when_athena_unavailable(mock_s3, client, admin_headers):
    """Si S3 est inaccessible, l'API renvoie un 503 propre."""
    resp = client.get("/api/dashboard/peak-hours", headers=admin_headers)
    assert resp.status_code == 503
    data = resp.json()
    assert data["source"] == "S3"
    assert "reason" in data



@patch("app.routes.stations.s3_service.get_all_stations",
       side_effect=DataSourceUnavailable("S3", "Credentials AWS non configurés"))
def test_stations_returns_503_when_s3_unavailable(mock_s3, client, auth_headers):
    """Si S3 est inaccessible, /stations renvoie un 503 propre."""
    resp = client.get("/api/stations", headers=auth_headers)
    assert resp.status_code == 503
    data = resp.json()
    assert data["source"] == "S3"

