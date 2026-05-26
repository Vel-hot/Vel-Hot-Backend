"""Tests des endpoints /stations"""


def test_get_toutes_les_stations(client):
    """Vérifie qu'on récupère bien toutes les stations."""
    response = client.get("/stations")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 4
    # Vérifier la structure de la réponse
    premiere = data[0]
    assert "id" in premiere
    assert "nom" in premiere
    assert "latitude" in premiere
    assert "longitude" in premiere
    assert "etat" in premiere


def test_get_station_par_id(client):
    """Vérifie qu'on récupère une station par son ID."""
    response = client.get("/stations/1")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == 1
    assert data["nom"] == "Bellecour"


def test_station_introuvable(client):
    """Vérifie qu'on reçoit un 404 pour une station inexistante."""
    response = client.get("/stations/9999")
    assert response.status_code == 404


def test_filtre_commune(client):
    """Vérifie le filtre par commune."""
    response = client.get("/stations?commune=Lyon")
    assert response.status_code == 200
    data = response.json()
    assert all(s["commune"] == "Lyon" for s in data)


def test_etat_station_vide(client):
    """Vérifie que la station Perrache (0% de vélos) a l'état 'vide'."""
    response = client.get("/stations/2")
    assert response.status_code == 200
    data = response.json()
    assert data["etat"] == "vide"


def test_etat_station_disponible(client):
    """Vérifie que la station Bellecour (25%) a l'état 'disponible'."""
    response = client.get("/stations/1")
    assert response.status_code == 200
    data = response.json()
    assert data["etat"] == "disponible"
