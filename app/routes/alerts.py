from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db_silver, get_db_gold
from app.schemas import AlerteSchema, AbonnementCreate, AbonnementResponse
from app.models import Station
from app.services.alert_service import (
    get_alertes_actives,
    creer_abonnement,
    detecter_alertes_depuis_predictions,
)
from app.services.station_service import get_station_par_id

router = APIRouter()


@router.get(
    "/active",
    response_model=list[AlerteSchema],
    summary="Toutes les alertes actives sur le réseau en ce moment",
    description="""
    Retourne les alertes des 60 dernières minutes pour toutes les stations.
    Une alerte est générée quand une station va être pleine ou vide dans moins de 30 min.
    """,
)
def get_alertes(
    db_silver: Session = Depends(get_db_silver),
    db_gold:   Session = Depends(get_db_gold),
):
    # Génère les nouvelles alertes depuis les prédictions ML
    detecter_alertes_depuis_predictions(db_gold, db_silver)

    # Récupère toutes les alertes actives
    alertes = get_alertes_actives(db_silver)

    resultats = []
    for alerte in alertes:
        # Récupérer le nom de la station pour le message
        station = db_silver.query(Station).filter(Station.id == alerte.station_id).first()
        nom_station = station.nom if station else f"Station #{alerte.station_id}"

        resultats.append(
            AlerteSchema(
                id                = alerte.id,
                station_id        = alerte.station_id,
                station_nom       = nom_station,
                type_alerte       = alerte.type_alerte,
                minutes_restantes = alerte.minutes_restantes,
                timestamp         = alerte.timestamp,
            )
        )

    return resultats


@router.post(
    "/subscribe",
    response_model=AbonnementResponse,
    status_code=201,
    summary="S'abonner aux alertes d'une station",
    description="""
    Enregistre un abonnement aux alertes pour une station donnée.
    
    - Si un **email** est fourni, des notifications pourront être envoyées.
    - Un **token** unique est retourné pour identifier l'abonnement (utile pour se désabonner plus tard).
    """,
)
def subscribe_alerte(
    body: AbonnementCreate,
    db:   Session = Depends(get_db_silver),
):
    # Vérifier que la station existe
    station = get_station_par_id(db, body.station_id)
    if not station:
        raise HTTPException(status_code=404, detail=f"Station {body.station_id} introuvable")

    abonnement = creer_abonnement(db, body.station_id, body.email)

    return AbonnementResponse(
        message    = f"Abonnement aux alertes de la station '{station.nom}' enregistré",
        station_id = body.station_id,
        token      = abonnement.token,
    )
