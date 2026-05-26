"""Tests des endpoints /alerts"""


def test_get_alertes_actives(client):
    """Vérifie que l'endpoint répond correctement."""
    response = client.get("/alerts/active")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_subscribe_alerte(client):
    """Vérifie qu'on peut s'abonner aux alertes d'une station."""
    response = client.post("/alerts/subscribe", json={
        "station_id": 1,
        "email": "test@velhhot.app"
    })
    assert response.status_code == 201
    data = response.json()
    assert data["station_id"] == 1
    assert "token" in data
    assert len(data["token"]) > 0


def test_subscribe_station_inexistante(client):
    """Vérifie qu'on reçoit un 404 pour une station inexistante."""
    response = client.post("/alerts/subscribe", json={"station_id": 9999})
    assert response.status_code == 404


def test_subscribe_sans_email(client):
    """Vérifie qu'on peut s'abonner sans email."""
    response = client.post("/alerts/subscribe", json={"station_id": 2})
    assert response.status_code == 201
