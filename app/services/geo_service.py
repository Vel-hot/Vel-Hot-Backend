import math


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calcule la distance en mètres entre deux points GPS.
    Utilise la formule de Haversine (distance réelle sur le globe).
    
    Args:
        lat1, lon1 : coordonnées du point de départ
        lat2, lon2 : coordonnées du point d'arrivée
    
    Returns:
        Distance en mètres
    """
    R = 6_371_000  # rayon de la Terre en mètres

    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c


def trouver_stations_proches(
    station_origine,
    toutes_les_stations: list,
    rayon_metres: float = 500,
    n_max: int = 5,
) -> list:
    """
    Retourne les N stations les plus proches dans le rayon donné,
    triées du plus proche au plus éloigné.
    
    Args:
        station_origine   : la station de référence (objet Station SQLAlchemy)
        toutes_les_stations : liste de toutes les stations
        rayon_metres      : rayon de recherche en mètres (défaut 500m)
        n_max             : nombre maximum de résultats (défaut 5)
    
    Returns:
        Liste de tuples (station, distance_metres) triée par distance
    """
    resultats = []

    for station in toutes_les_stations:
        # On exclut la station d'origine
        if station.id == station_origine.id:
            continue

        distance = haversine(
            station_origine.latitude,
            station_origine.longitude,
            station.latitude,
            station.longitude,
        )

        if distance <= rayon_metres:
            resultats.append((station, round(distance, 1)))

    # Trier par distance croissante et limiter au nombre max
    resultats.sort(key=lambda x: x[1])
    return resultats[:n_max]
