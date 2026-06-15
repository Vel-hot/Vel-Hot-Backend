"""Tests pour /stations, /stations/{id}, /predict, /alerts — S3 mocké."""
from unittest.mock import patch

FAKE_STATIONS = [
    {
        "station_id": "1", "name": "Bellecour", "lat": 45.757, "lon": 4.832,
        "capacity": 20, "num_bikes_available": 12, "num_docks_available": 8,
        "fill_rate": 0.6, "status": "OPEN", "hour": 14,
        "hour_sin": 0.5, "hour_cos": 0.5, "dow_sin": 0.3, "dow_cos": 0.7,
        "is_weekend": False, "timestamp": "2026-06-15T14:00:00",
    },
    {
        "station_id": "2", "name": "Perrache", "lat": 45.749, "lon": 4.826,
        "capacity": 15, "num_bikes_available": 3, "num_docks_available": 12,
        "fill_rate": 0.2, "status": "OPEN", "hour": 14,
        "hour_sin": 0.5, "hour_cos": 0.5, "dow_sin": 0.3, "dow_cos": 0.7,
        "is_weekend": False, "timestamp": "2026-06-15T14:00:00",
    },
]

FAKE_PREDICTIONS = [
    {"station_id": "1", "pred_t15": 0.58, "pred_t30": 0.55, "pred_t60": 0.50},
]

FAKE_ALERTS_PREDICTIONS = [
    {"station_id": "3", "pred_t15": 0.05, "pred_t30": 0.04, "pred_t60": 0.03},
    {"station_id": "4", "pred_t15": 0.92, "pred_t30": 0.95, "pred_t60": 0.97},
    {"station_id": "5", "pred_t15": 0.5,  "pred_t30": 0.5,  "pred_t60": 0.5},
]


@patch("app.routes.stations.s3_service.get_all_stations", return_value=FAKE_STATIONS)
@patch("app.services.historique_service.save_snapshot")  # éviter l'écriture en base
def test_list_stations(mock_save, mock_get, client, auth_headers):
    resp = client.get("/stations", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    assert data[0]["station_id"] == "1"
    assert data[0]["fill_rate"] == 0.6


@patch("app.routes.stations.s3_service.get_all_stations", return_value=[])
@patch("app.services.historique_service.save_snapshot")
def test_list_stations_empty(mock_save, mock_get, client, auth_headers):
    resp = client.get("/stations", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json() == []


@patch("app.routes.stations.s3_service.get_predictions", return_value=FAKE_PREDICTIONS)
@patch("app.routes.stations.s3_service.get_station_by_id", return_value=FAKE_STATIONS[0])
def test_get_station_by_id_with_predictions(mock_station, mock_preds, client, auth_headers):
    resp = client.get("/stations/1", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["station_id"] == "1"
    assert data["predictions"]["t15"] == 0.58
    assert data["predictions"]["t30"] == 0.55
    assert data["predictions"]["t60"] == 0.50


@patch("app.routes.stations.s3_service.get_station_by_id", return_value=None)
def test_get_station_not_found(mock_station, client, auth_headers):
    resp = client.get("/stations/999", headers=auth_headers)
    assert resp.status_code == 404


@patch("app.routes.predictions.s3_service.get_predictions", return_value=FAKE_PREDICTIONS)
def test_predict_endpoint(mock_preds, client, auth_headers):
    resp = client.get("/predict?station_id=1", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["station_id"] == "1"
    assert data["predictions"]["t30"] == 0.55


@patch("app.routes.predictions.s3_service.get_predictions", return_value=[])
def test_predict_not_found(mock_preds, client, auth_headers):
    resp = client.get("/predict?station_id=999", headers=auth_headers)
    assert resp.status_code == 404


@patch("app.routes.alerts.s3_service.get_predictions", return_value=FAKE_ALERTS_PREDICTIONS)
def test_alerts_empty_and_full(mock_preds, client, auth_headers):
    resp = client.get("/alerts", headers=auth_headers)
    assert resp.status_code == 200
    alerts = resp.json()["alerts"]

    types = {a["station_id"]: a["type"] for a in alerts}
    assert types["3"] == "EMPTY"   # pred_t30 = 0.04 < 0.1
    assert types["4"] == "FULL"    # pred_t30 = 0.95 > 0.9
    assert "5" not in types        # pred_t30 = 0.5 → pas d'alerte
