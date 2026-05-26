# velhhot-backend

API FastAPI pour la plateforme Vél'hot — prédiction de disponibilité des stations Vélo'v de Lyon.

## Stack

- **FastAPI** — framework API REST
- **SQLAlchemy** — ORM pour Aurora PostgreSQL
- **Pydantic** — validation des données
- **PostgreSQL** (local) / **Aurora PostgreSQL** (AWS en production)

## Installation

```bash
# 1. Cloner le repo
git clone https://github.com/velhhot/velhhot-backend
cd velhhot-backend

# 2. Créer l'environnement virtuel
python -m venv venv
source venv/bin/activate        # Mac / Linux
venv\Scripts\activate           # Windows

# 3. Installer les dépendances
pip install -r requirements.txt

# 4. Configurer les variables d'environnement
cp .env.example .env
# Éditer .env avec tes valeurs locales

# 5. Créer les bases locales (PostgreSQL doit être installé)
createdb velohot_silver
createdb velohot_gold

# 6. Lancer le serveur
uvicorn main:app --reload
```

## Endpoints disponibles

| Méthode | Route | Description |
|---------|-------|-------------|
| GET | `/` | Health check |
| GET | `/stations` | Liste des stations avec disponibilité temps réel |
| GET | `/stations/{id}` | Détail d'une station |
| GET | `/stations/{id}/predictions` | Prédictions T+15, T+30, T+60 min |
| GET | `/stations/{id}/alternatives` | Stations proches avec des vélos |
| GET | `/alerts/active` | Alertes actives sur le réseau |
| POST | `/alerts/subscribe` | S'abonner aux alertes d'une station |
| GET | `/analytics/top-stations` | Top des stations les plus utilisées |
| GET | `/analytics/trends` | Utilisation par heure et jour de semaine |
| GET | `/analytics/heatmap` | Données pour la carte thermique |

## Documentation Swagger

Une fois le serveur lancé, la doc interactive est disponible sur :

- **Swagger UI** → http://localhost:8000/docs
- **ReDoc** → http://localhost:8000/redoc

## Tests

```bash
pytest app/tests/ -v
```

## Structure du projet

```
velhhot-backend/
├── main.py                   ← point d'entrée FastAPI
├── .env                      ← variables secrètes (non versionné)
├── .env.example              ← template à copier
├── requirements.txt
└── app/
    ├── config.py             ← lecture .env
    ├── database.py           ← connexion PostgreSQL
    ├── models.py             ← tables SQLAlchemy
    ├── schemas.py            ← validation Pydantic
    ├── routes/               ← endpoints par ressource
    │   ├── stations.py
    │   ├── predictions.py
    │   ├── alternatives.py
    │   ├── alerts.py
    │   └── analytics.py
    ├── services/             ← logique métier
    │   ├── station_service.py
    │   ├── alert_service.py
    │   └── geo_service.py
    └── tests/
        ├── conftest.py       ← données fictives SQLite
        ├── test_stations.py
        └── test_alerts.py
```

## Branches Git

- `main` → production uniquement
- `develop` → développement en cours
- `feature/xxx` → une branche par tâche

## Variables d'environnement

| Variable | Description | Exemple |
|----------|-------------|---------|
| `DATABASE_URL` | Connexion velohot_silver | `postgresql://user:pass@localhost/velohot_silver` |
| `DATABASE_GOLD_URL` | Connexion velohot_gold | `postgresql://user:pass@localhost/velohot_gold` |
| `AWS_REGION` | Région AWS | `eu-west-3` |
| `ENV` | Environnement | `development` ou `production` |
