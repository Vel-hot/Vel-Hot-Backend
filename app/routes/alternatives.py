from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db_silver
from app.schemas import StationAlternative
from app.services.station_service import (
    get_station_par_id,
    get_toutes_les_stations,
    get_derniers_statuts_toutes_stations,
)
from app.services.geo_service import trouver_stations_proches

router = APIRouter()


@router.get(
    "/{station_id}/alternatives",
    response_model=list[StationAlternative],
    summary="Stations alternatives proches avec des vélos disponibles",
    description="""
    Retourne les stations les plus proches de la station demandée
    qui ont encore des vélos disponibles.
    
    Les résultats sont triés du plus proche au plus éloigné.
    
    Paramètres :
    - **radius** : rayon de recherche en mètres (défaut 500m, max 2000m)
    - **n**      : nombre maximum de résultats (défaut 5, max 10)
    """,
)
def get_alternatives(
    station_id: int,
    radius: int     = Query(500,  ge=100, le=2000, description="Rayon de recherche en mètres"),
    n:      int     = Query(5,    ge=1,   le=10,   description="Nombre maximum de résultats"),
    db:     Session = Depends(get_db_silver),
):
    # Vérifier que la station d'origine existe
    station_origine = get_station_par_id(db, station_id)
    if not station_origine:
        raise HTTPException(status_code=404, detail=f"Station {station_id} introuvable")

    # Récupérer toutes les stations et leurs statuts
    toutes_stations = get_toutes_les_stations(db)
    statuts         = get_derniers_statuts_toutes_stations(db)

    # Garder uniquement les stations avec des vélos disponibles
    stations_avec_velos = [
        s for s in toutes_stations
        if statuts.get(s.id) and statuts[s.id].velos_dispo > 0
    ]

    # Trouver les stations proches dans le rayon demandé
    stations_proches = trouver_stations_proches(
        station_origine,
        stations_avec_velos,
        rayon_metres=radius,
        n_max=n,
    )

    if not stations_proches:
        # Aucune alternative dans le rayon → on élargit automatiquement à 1000m
        stations_proches = trouver_stations_proches(
            station_origine,
            stations_avec_velos,
            rayon_metres=1000,
            n_max=n,
        )

    resultats = []
    for station, distance in stations_proches:
        statut = statuts.get(station.id)
        resultats.append(
            StationAlternative(
                id               = station.id,
                nom              = station.nom,
                commune          = station.commune,
                adresse          = station.adresse,
                latitude         = station.latitude,
                longitude        = station.longitude,
                capacite_totale  = station.capacite_totale,
                distance_metres  = distance,
                velos_dispo      = statut.velos_dispo if statut else 0,
                places_dispo     = statut.places_dispo if statut else 0,
                taux_remplissage = statut.taux_remplissage if statut else 0,
            )
        )

    return resultats
