"""Fixtures partagées : base SQLite en mémoire + client de test FastAPI.

On surcharge DATABASE_URL et JWT_SECRET via variables d'environnement
AVANT d'importer l'app, pour ne jamais toucher à la vraie base Aurora/locale.
"""
import os

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["JWT_SECRET"]   = "test-secret-key-for-pytest-only"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from main import app


@pytest.fixture(scope="function")
def db_session():
    """Base SQLite en mémoire, recréée pour chaque test."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)

    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db_session):
    """TestClient FastAPI avec la base de test injectée via dependency override."""
    def _override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def registered_user(client):
    """Crée un compte 'user' et retourne (email, password)."""
    payload = {
        "nom": "Test", "prenom": "User",
        "email": "user@test.com", "password": "motdepasse123",
    }
    resp = client.post("/auth/register", json=payload)
    assert resp.status_code == 201
    return payload


@pytest.fixture
def auth_headers(client, registered_user):
    """Retourne les headers Authorization avec un token valide (rôle user)."""
    resp = client.post("/auth/login", json={
        "email": registered_user["email"],
        "password": registered_user["password"],
    })
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin_headers(client, db_session):
    """Crée un compte admin directement en base et retourne ses headers."""
    from app.auth import create_access_token, hash_password
    from app.models import Utilisateur

    admin = Utilisateur(
        nom="Admin", prenom="Test", email="admin@test.com",
        hashed_password=hash_password("adminpass123"), role="admin",
    )
    db_session.add(admin)
    db_session.commit()
    db_session.refresh(admin)

    token = create_access_token({"sub": str(admin.id), "email": admin.email, "role": admin.role})
    return {"Authorization": f"Bearer {token}"}
