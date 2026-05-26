from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc
from datetime import datetime

from app.database import get_db_silver, get_db_gold
from app.schemas import PredictionSchema
from app.models import Prediction, StatutStation
from app.services.alert_service import construire_message_alerte, SEUIL_ALERTE_PLEINE, SEUIL_ALERTE_VIDE
from app.services.station_service import get_station_par_id

router = APIRouter()


@router.get(
    "/{station_id}/predictions",
    response_model=PredictionSchema,
    summary="Prédictions de remplissage pour une station (T+15, T+30, T+60 min)",
    description="""
    Retourne les prédictions générées par le modèle LSTM pour une station donnée.
    
    - **t_plus_15** : taux de remplissage prédit dans 15 minutes
    - **t_plus_30** : taux de remplissage prédit dans 30 minutes  
    - **t_plus_60** : taux de remplissage prédit dans 60 minutes
    - **alerte**    : message si saturation ou vidage imminent
    
    Ces données sont produites par l'équipe ML via SageMaker.
    """,
)
def get_predictions(
    station_id: int,
    db_silver:  Session = Depends(get_db_silver),
    db_gold:    Session = Depends(get_db_gold),
):
    # Vérifier que la station existe
    station = get_station_par_id(db_silver, station_id)
    if not station:
        raise HTTPException(status_code=404, detail=f"Station {station_id} introuvable")

    # Récupérer le statut actuel
    statut_actuel = (
        db_silver.query(StatutStation)
        .filter(StatutStation.station_id == station_id)
        .order_by(desc(StatutStation.timestamp))
        .first()
    )
    taux_actuel = statut_actuel.taux_remplissage if statut_actuel else 0.0

    # Récupérer la dernière prédiction disponible pour cette station
    prediction = (
        db_gold.query(Prediction)
        .filter(Prediction.station_id == station_id)
        .order_by(desc(Prediction.timestamp))
        .first()
    )

    if not prediction:
        # Pas encore de prédiction ML disponible → on retourne juste le taux actuel
        return PredictionSchema(
            station_id  = station_id,
            taux_actuel = taux_actuel,
            t_plus_15   = None,
            t_plus_30   = None,
            t_plus_60   = None,
            confiance   = None,
            timestamp   = datetime.utcnow(),
            alerte      = None,
        )

    # Construire le message d'alerte si nécessaire
    message_alerte = None
    if prediction.t_plus_15 is not None:
        if prediction.t_plus_15 >= SEUIL_ALERTE_PLEINE:
            message_alerte = construire_message_alerte("pleine", 15, station.nom)
        elif prediction.t_plus_15 <= SEUIL_ALERTE_VIDE:
            message_alerte = construire_message_alerte("vide", 15, station.nom)
    elif prediction.t_plus_30 is not None:
        if prediction.t_plus_30 >= SEUIL_ALERTE_PLEINE:
            message_alerte = construire_message_alerte("pleine", 30, station.nom)
        elif prediction.t_plus_30 <= SEUIL_ALERTE_VIDE:
            message_alerte = construire_message_alerte("vide", 30, station.nom)

    return PredictionSchema(
        station_id  = station_id,
        taux_actuel = taux_actuel,
        t_plus_15   = prediction.t_plus_15,
        t_plus_30   = prediction.t_plus_30,
        t_plus_60   = prediction.t_plus_60,
        confiance   = prediction.confiance,
        timestamp   = prediction.timestamp,
        alerte      = message_alerte,
    )
