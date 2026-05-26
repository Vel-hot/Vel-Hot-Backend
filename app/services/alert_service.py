import secrets
from sqlalchemy.orm import Session
from sqlalchemy import desc
from datetime import datetime, timedelta
from app.models import Alerte, AbonnementAlerte, Prediction


SEUIL_ALERTE_PLEINE = 90   # station considérée pleine au-delà de 90%
SEUIL_ALERTE_VIDE   = 10   # station considérée vide en-dessous de 10%


def detecter_alertes_depuis_predictions(db_gold: Session, db_silver: Session) -> list[Alerte]:
    """
    Analyse les prédictions et génère des alertes si une station
    va être pleine ou vide dans moins de 30 minutes.
    
    Appelé par l'endpoint GET /alerts/active.
    """
    # Prédictions récentes (moins de 10 minutes)
    limite = datetime.utcnow() - timedelta(minutes=10)
    predictions = (
        db_gold.query(Prediction)
        .filter(Prediction.timestamp >= limite)
        .all()
    )

    alertes_generees = []

    for pred in predictions:
        # Vérifier T+15 minutes
        if pred.t_plus_15 is not None:
            if pred.t_plus_15 >= SEUIL_ALERTE_PLEINE:
                alerte = _creer_alerte(db_silver, pred.station_id, "pleine", 15)
                if alerte:
                    alertes_generees.append(alerte)

            elif pred.t_plus_15 <= SEUIL_ALERTE_VIDE:
                alerte = _creer_alerte(db_silver, pred.station_id, "vide", 15)
                if alerte:
                    alertes_generees.append(alerte)

        # Vérifier T+30 minutes (seulement si pas déjà alerté à T+15)
        elif pred.t_plus_30 is not None:
            if pred.t_plus_30 >= SEUIL_ALERTE_PLEINE:
                alerte = _creer_alerte(db_silver, pred.station_id, "pleine", 30)
                if alerte:
                    alertes_generees.append(alerte)

            elif pred.t_plus_30 <= SEUIL_ALERTE_VIDE:
                alerte = _creer_alerte(db_silver, pred.station_id, "vide", 30)
                if alerte:
                    alertes_generees.append(alerte)

    return alertes_generees


def _creer_alerte(db: Session, station_id: int, type_alerte: str, minutes: int) -> Alerte | None:
    """
    Crée une alerte en base si aucune alerte du même type
    n'existe déjà pour cette station dans les 30 dernières minutes.
    Évite les doublons d'alertes.
    """
    limite = datetime.utcnow() - timedelta(minutes=30)
    alerte_existante = (
        db.query(Alerte)
        .filter(
            Alerte.station_id  == station_id,
            Alerte.type_alerte == type_alerte,
            Alerte.timestamp   >= limite,
        )
        .first()
    )

    if alerte_existante:
        return None  # alerte déjà présente, on ne duplique pas

    nouvelle_alerte = Alerte(
        station_id=station_id,
        type_alerte=type_alerte,
        minutes_restantes=minutes,
        active=True,
    )
    db.add(nouvelle_alerte)
    db.commit()
    db.refresh(nouvelle_alerte)
    return nouvelle_alerte


def get_alertes_actives(db: Session) -> list:
    """Retourne toutes les alertes actives des 60 dernières minutes."""
    limite = datetime.utcnow() - timedelta(minutes=60)
    return (
        db.query(Alerte)
        .filter(Alerte.active == True, Alerte.timestamp >= limite)
        .order_by(desc(Alerte.timestamp))
        .all()
    )


def creer_abonnement(db: Session, station_id: int, email: str = None) -> AbonnementAlerte:
    """
    Enregistre l'abonnement d'un utilisateur aux alertes d'une station.
    Génère un token unique pour identifier l'abonné.
    """
    token = secrets.token_urlsafe(16)

    abonnement = AbonnementAlerte(
        station_id=station_id,
        email=email,
        token=token,
    )
    db.add(abonnement)
    db.commit()
    db.refresh(abonnement)
    return abonnement


def construire_message_alerte(type_alerte: str, minutes: int, nom_station: str) -> str:
    """Retourne un message lisible pour l'utilisateur (affiché dans React)."""
    if type_alerte == "pleine":
        return f"⚠️ La station {nom_station} sera pleine dans environ {minutes} min"
    else:
        return f"⚠️ La station {nom_station} sera vide dans environ {minutes} min"
