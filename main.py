from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import create_tables
from app.routes import stations, predictions, alternatives, alerts, analytics

app = FastAPI(
    title="Vél'hot API",
    description="""
    API de prédiction de disponibilité des stations Vélo'v de Lyon.
    
    ## Fonctionnalités
    - **Stations** : disponibilité en temps réel des 428 stations
    - **Prédictions** : remplissage prévu à T+15, T+30 et T+60 minutes
    - **Alternatives** : stations proches avec des vélos disponibles
    - **Alertes** : notifications de saturation imminente
    - **Analytics** : statistiques pour les analystes de la ville
    """,
    version="1.0.0",
    contact={"name": "Équipe Vél'hot"},
)

# Autoriser les appels depuis React (localhost:3000 en dev, domaine prod)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",  # Vite
        "https://velhhot.app",   # domaine production à adapter
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Enregistrement des routes
app.include_router(stations.router,     prefix="/stations",   tags=["Stations"])
app.include_router(predictions.router,  prefix="/stations",   tags=["Prédictions"])
app.include_router(alternatives.router, prefix="/stations",   tags=["Alternatives"])
app.include_router(alerts.router,       prefix="/alerts",     tags=["Alertes"])
app.include_router(analytics.router,    prefix="/analytics",  tags=["Analytics"])


@app.on_event("startup")
def startup():
    """Crée les tables en base au démarrage si elles n'existent pas encore."""
    create_tables()


@app.get("/", tags=["Santé"])
def health_check():
    """Vérifie que l'API est bien en ligne."""
    return {"status": "ok", "message": "Vél'hot API opérationnelle"}
