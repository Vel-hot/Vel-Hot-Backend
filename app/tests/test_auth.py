"""Tests pour /auth/register, /auth/login, /auth/me."""


def test_register_success(client):
    resp = client.post("/api/auth/register", json={
        "nom": "Dupont", "prenom": "Jean",
        "email": "jean.dupont@test.com", "password": "motdepasse123",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["email"] == "jean.dupont@test.com"
    assert data["role"] == "user"
    assert "hashed_password" not in data  # ne doit jamais fuiter


def test_register_duplicate_email(client, registered_user):
    resp = client.post("/api/auth/register", json={
        "nom": "Autre", "prenom": "Personne",
        "email": registered_user["email"], "password": "autremotdepasse",
    })
    assert resp.status_code == 409


def test_login_success(client, registered_user):
    resp = client.post("/api/auth/login", json={
        "email": registered_user["email"],
        "password": registered_user["password"],
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_login_wrong_password(client, registered_user):
    resp = client.post("/api/auth/login", json={
        "email": registered_user["email"],
        "password": "mauvais_mdp",
    })
    assert resp.status_code == 401


def test_login_unknown_email(client):
    resp = client.post("/api/auth/login", json={
        "email": "inconnu@test.com",
        "password": "peu importe",
    })
    assert resp.status_code == 401


def test_me_returns_profile(client, auth_headers, registered_user):
    resp = client.get("/api/auth/me", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["email"] == registered_user["email"]
    assert data["role"] == "user"


def test_me_without_token(client):
    resp = client.get("/api/auth/me")
    assert resp.status_code in (401, 403)


def test_protected_endpoint_without_token(client):
    resp = client.get("/api/stations")
    assert resp.status_code in (401, 403)

