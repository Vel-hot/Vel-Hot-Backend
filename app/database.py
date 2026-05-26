from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from app.config import settings

# --- Moteurs de connexion ---
# velohot_silver : données temps réel (stations, statuts)
engine_silver = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,   # vérifie la connexion avant chaque requête
    pool_size=10,
    max_overflow=20,
    echo=settings.DEBUG,  # affiche les requêtes SQL en mode dev
)

# velohot_gold : prédictions du modèle ML
engine_gold = create_engine(
    settings.DATABASE_GOLD_URL,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    echo=settings.DEBUG,
)

# --- Sessions ---
SessionSilver = sessionmaker(bind=engine_silver, autocommit=False, autoflush=False)
SessionGold   = sessionmaker(bind=engine_gold,   autocommit=False, autoflush=False)


# --- Classe de base pour les modèles SQLAlchemy ---
class Base(DeclarativeBase):
    pass


# --- Dépendances FastAPI (injectées dans les routes) ---
def get_db_silver():
    """Retourne une session vers velohot_silver (données temps réel)."""
    db = SessionSilver()
    try:
        yield db
    finally:
        db.close()


def get_db_gold():
    """Retourne une session vers velohot_gold (prédictions ML)."""
    db = SessionGold()
    try:
        yield db
    finally:
        db.close()


def create_tables():
    """Crée toutes les tables si elles n'existent pas encore."""
    from app import models  # import ici pour éviter les imports circulaires
    Base.metadata.create_all(bind=engine_silver)
    Base.metadata.create_all(bind=engine_gold)
