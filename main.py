from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.database import create_tables, SessionLocal
from app.exceptions import DataSourceUnavailable
from app.logging_config import get_logger, setup_logging
from app.routes import auth, stations, predictions, alerts, dashboard, historique

setup_logging()
logger = get_logger(__name__)

app = FastAPI(
    title="Vél'hot API",
    description="""
API de prédiction de disponibilité des stations Vélo'v de Lyon.

## Authentification
1. `POST /auth/register` — créer un compte (nom, prénom, email, password)
2. `POST /auth/login` — obtenir un JWT
3. `GET /auth/me` — profil de l'utilisateur connecté
4. Cliquer **Authorize** → coller le token brut (sans `Bearer`)

## Rôles
- **user** : stations, prédictions, alertes, historique
- **analyste** / **admin** : + dashboard (peak-hours, heatmap)
""",
    version="2.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://velhhot.app", "http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

API_Prefix = "/api"
app.include_router(auth.router,        prefix=f"{API_Prefix}/auth",        tags=["Auth"])
app.include_router(stations.router,    prefix=f"{API_Prefix}/stations",    tags=["Stations"])
app.include_router(predictions.router, prefix=f"{API_Prefix}/predict",     tags=["Prédictions"])
app.include_router(alerts.router,      prefix=f"{API_Prefix}/alerts",      tags=["Alertes"])
app.include_router(dashboard.router,   prefix=f"{API_Prefix}/dashboard",   tags=["Dashboard"])
app.include_router(historique.router,  prefix=f"{API_Prefix}/historique",  tags=["Historique"])


@app.exception_handler(DataSourceUnavailable)
async def data_source_unavailable_handler(request: Request, exc: DataSourceUnavailable):
    """S3/Athena inaccessible → 503 propre au lieu d'un 500 brut."""
    logger.error("Source de données indisponible [%s] sur %s : %s",
                  exc.source, request.url.path, exc.detail)
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={
            "detail": f"Service temporairement indisponible ({exc.source})",
            "source": exc.source,
            "reason": exc.detail,
        },
    )


@app.on_event("startup")
def startup():
    create_tables()
    logger.info("Vél'hot API démarrée (env=%s)", __import__("app.config", fromlist=["settings"]).settings.ENV)


@app.get("/api/health", tags=["Santé"])
def health_check():
    """Health check public — utilisé par AWS ALB / ECS / App Runner."""
    db_ok = False
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        db_ok = True
    except Exception:
        pass

    payload = {
        "status": "ok" if db_ok else "degraded",
        "version": "2.1.0",
        "checks": {"database": "ok" if db_ok else "unreachable"},
    }
    return JSONResponse(
        content=payload,
        status_code=status.HTTP_200_OK if db_ok else status.HTTP_503_SERVICE_UNAVAILABLE,
    )


@app.get("/", tags=["Santé"])
def root():
    """Redirect implicite vers /health — conservé pour compatibilité."""
    return {"status": "ok", "version": "2.1.0"}


def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    schema = get_openapi(title=app.title, version=app.version,
                          description=app.description, routes=app.routes)
    schema["components"]["securitySchemes"] = {
        "BearerAuth": {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"}
    }
    for path in schema["paths"].values():
        for method in path.values():
            method["security"] = [{"BearerAuth": []}]
    app.openapi_schema = schema
    return schema


app.openapi = custom_openapi
