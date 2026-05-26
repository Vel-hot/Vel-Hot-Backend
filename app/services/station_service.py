from sqlalchemy.orm import Session
from sqlalchemy import desc
from app.models import Station, StatutStation


def get_toutes_les_stations(db: Session, commune: str = None) -> list:
    """
    Retourne toutes les stations actives avec leur dernier statut connu.
    
    Args:
        db      : session base de données
        commune : filtre optionnel par commune (ex: "Lyon")
    """
    query = db.query(Station).filter(Station.est_active == True)

    if commune:
        query = query.filter(Station.commune.ilike(f"%{commune}%"))

    return query.all()


def get_station_par_id(db: Session, station_id: int) -> Station | None:
    """Retourne une station par son identifiant, ou None si introuvable."""
    return db.query(Station).filter(Station.id == station_id).first()


def get_dernier_statut(db: Session, station_id: int) -> StatutStation | None:
    """
    Retourne le statut le plus récent d'une station.
    C'est ce statut qui est mis à jour toutes les 5 min par la Lambda.
    """
    return (
        db.query(StatutStation)
        .filter(StatutStation.station_id == station_id)
        .order_by(desc(StatutStation.timestamp))
        .first()
    )


def get_derniers_statuts_toutes_stations(db: Session) -> dict:
    """
    Retourne un dictionnaire {station_id: dernier_statut} pour toutes les stations.
    Optimisé pour éviter N+1 requêtes quand on affiche la liste complète.
    """
    # On récupère tous les statuts triés par date décroissante
    tous_statuts = (
        db.query(StatutStation)
        .order_by(desc(StatutStation.timestamp))
        .all()
    )

    # On garde uniquement le plus récent par station
    statuts_par_station = {}
    for statut in tous_statuts:
        if statut.station_id not in statuts_par_station:
            statuts_par_station[statut.station_id] = statut

    return statuts_par_station


def calculer_etat(taux_remplissage: float) -> str:
    """
    Retourne un label d'état lisible selon le taux de remplissage.
    
    Utilisé pour colorier les markers sur la carte React :
    - vide / presque_vide → rouge / orange
    - disponible → vert
    - presque_pleine / pleine → orange / rouge
    """
    if taux_remplissage <= 5:
        return "vide"
    elif taux_remplissage <= 20:
        return "presque_vide"
    elif taux_remplissage <= 80:
        return "disponible"
    elif taux_remplissage <= 95:
        return "presque_pleine"
    else:
        return "pleine"
