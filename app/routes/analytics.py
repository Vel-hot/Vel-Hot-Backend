from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, extract
from datetime import datetime, timedelta
from typing import Optional

from app.database import get_db_silver
from app.schemas import TopStation, TendanceHeure, HeatmapPoint
from app.models import Station, StatutStation

router = APIRouter()

JOURS_SEMAINE = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]


@router.get(
    "/top-stations",
    response_model=list[TopStation],
    summary="Top des stations les plus utilisées",
    description="""
    Retourne les stations avec le plus grand nombre de rotations
    (vélos pris + déposés) sur la période choisie.
    
    Paramètres :
    - **jours** : nombre de jours à analyser en arrière (défaut 7)
    - **limite** : nombre de stations à retourner (défaut 10)
    """,
)
def get_top_stations(
    jours:  int     = Query(7,  ge=1, le=90,  description="Nombre de jours analysés"),
    limite: int     = Query(10, ge=1, le=50,  description="Nombre de résultats"),
    db:     Session = Depends(get_db_silver),
):
    depuis = datetime.utcnow() - timedelta(days=jours)

    # Calcul des rotations : on approxime par l'écart-type du taux de remplissage
    # (plus une station varie, plus elle est utilisée)
    resultats = (
        db.query(
            Station.id,
            Station.nom,
            Station.commune,
            func.count(StatutStation.id).label("nb_rotations"),
        )
        .join(StatutStation, Station.id == StatutStation.station_id)
        .filter(StatutStation.timestamp >= depuis)
        .group_by(Station.id, Station.nom, Station.commune)
        .order_by(func.count(StatutStation.id).desc())
        .limit(limite)
        .all()
    )

    return [
        TopStation(
            station_id   = r.id,
            station_nom  = r.nom,
            commune      = r.commune,
            nb_rotations = r.nb_rotations,
        )
        for r in resultats
    ]


@router.get(
    "/trends",
    response_model=list[TendanceHeure],
    summary="Utilisation moyenne par heure et par jour de semaine",
    description="""
    Retourne le taux de remplissage moyen pour chaque heure de la journée.
    
    Paramètres :
    - **jour** : jour de la semaine (ex: `?jour=lundi`). Si absent, retourne tous les jours.
    - **commune** : filtrer par commune (ex: `?commune=Lyon`)
    """,
)
def get_trends(
    jour:    Optional[str] = Query(None, description="Jour de semaine : lundi, mardi..."),
    commune: Optional[str] = Query(None, description="Filtrer par commune"),
    db:      Session       = Depends(get_db_silver),
):
    depuis = datetime.utcnow() - timedelta(days=30)  # 30 derniers jours

    query = (
        db.query(
            extract("hour", StatutStation.timestamp).label("heure"),
            extract("dow", StatutStation.timestamp).label("dow"),   # 0=dimanche, 1=lundi...
            func.avg(StatutStation.taux_remplissage).label("taux_moyen"),
        )
        .join(Station, Station.id == StatutStation.station_id)
        .filter(StatutStation.timestamp >= depuis)
    )

    if commune:
        query = query.filter(Station.commune.ilike(f"%{commune}%"))

    resultats = (
        query
        .group_by("heure", "dow")
        .order_by("dow", "heure")
        .all()
    )

    tendances = []
    for r in resultats:
        # Convertir le numéro de jour (0=dimanche en PostgreSQL) en nom français
        dow = int(r.dow)
        nom_jour = JOURS_SEMAINE[(dow - 1) % 7]

        # Appliquer le filtre par jour si demandé
        if jour and nom_jour != jour.lower():
            continue

        tendances.append(
            TendanceHeure(
                heure           = int(r.heure),
                taux_moyen      = round(float(r.taux_moyen), 1),
                jour_de_semaine = nom_jour,
            )
        )

    return tendances


@router.get(
    "/heatmap",
    response_model=list[HeatmapPoint],
    summary="Données pour la carte thermique d'utilisation",
    description="""
    Retourne la position de chaque station avec une intensité normalisée
    représentant son niveau d'utilisation moyen.
    
    Utilisé par la carte thermique du dashboard React (Leaflet.heat).
    """,
)
def get_heatmap(
    db: Session = Depends(get_db_silver),
):
    depuis = datetime.utcnow() - timedelta(days=7)

    resultats = (
        db.query(
            Station.latitude,
            Station.longitude,
            func.avg(StatutStation.taux_remplissage).label("taux_moyen"),
        )
        .join(StatutStation, Station.id == StatutStation.station_id)
        .filter(StatutStation.timestamp >= depuis)
        .group_by(Station.latitude, Station.longitude)
        .all()
    )

    if not resultats:
        return []

    # Normaliser les intensités entre 0 et 1
    taux_max = max(r.taux_moyen for r in resultats) or 1

    return [
        HeatmapPoint(
            latitude  = r.latitude,
            longitude = r.longitude,
            intensite = round(float(r.taux_moyen) / taux_max, 3),
        )
        for r in resultats
    ]
