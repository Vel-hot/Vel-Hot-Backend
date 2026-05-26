from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db_silver
from app.schemas import StationAvecStatut, StatutBase
from app.services.station_service import (
    get_toutes_les_stations,
    get_station_par_id,
    get_dernier_statut,
    get_derniers_statuts_toutes_stations,
    calculer_etat,
)

router = APIRouter()


@router.get(
    "",
    response_model=list[StationAvecStatut],
    summary="Liste de toutes les stations avec disponibilité en temps réel",
    description="""
    Retourne les 428 stations Vélo'v avec leur statut actuel.
    Les données sont mises à jour toutes les 5 minutes par la Lambda d'ingestion.
    
    Filtres disponibles :
    - **commune** : filtrer par commune (ex: `?commune=Lyon`)
    - **etat** : filtrer par état (ex: `?etat=disponible`)
    """,
)
def get_stations(
    commune: Optional[str] = Query(None, description="Filtrer par commune"),
    etat:    Optional[str] = Query(None, description="Filtrer par état : disponible, vide, pleine..."),
    db:      Session       = Depends(get_db_silver),
):
    stations = get_toutes_les_stations(db, commune=commune)
    statuts  = get_derniers_statuts_toutes_stations(db)

    resultats = []
    for station in stations:
        statut = statuts.get(station.id)
        taux   = statut.taux_remplissage if statut else 0
        etat_station = calculer_etat(taux)

        # Appliquer le filtre par état si demandé
        if etat and etat_station != etat:
            continue

        resultats.append(
            StationAvecStatut(
                id              = station.id,
                nom             = station.nom,
                commune         = station.commune,
                adresse         = station.adresse,
                latitude        = station.latitude,
                longitude       = station.longitude,
                capacite_totale = station.capacite_totale,
                etat            = etat_station,
                statut          = StatutBase.model_validate(statut) if statut else None,
            )
        )

    return resultats


@router.get(
    "/{station_id}",
    response_model=StationAvecStatut,
    summary="Détail d'une station par son identifiant",
)
def get_station(
    station_id: int,
    db:         Session = Depends(get_db_silver),
):
    station = get_station_par_id(db, station_id)
    if not station:
        raise HTTPException(status_code=404, detail=f"Station {station_id} introuvable")

    statut = get_dernier_statut(db, station_id)
    taux   = statut.taux_remplissage if statut else 0

    return StationAvecStatut(
        id              = station.id,
        nom             = station.nom,
        commune         = station.commune,
        adresse         = station.adresse,
        latitude        = station.latitude,
        longitude       = station.longitude,
        capacite_totale = station.capacite_totale,
        etat            = calculer_etat(taux),
        statut          = StatutBase.model_validate(statut) if statut else None,
    )
