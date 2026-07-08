# Vél'hot — Backend

API FastAPI pour le projet Vél'hot (M2 ESGI — Projet Annuel).
Sert les données de disponibilité des stations Vélo'v de Lyon et leurs
prédictions ML à +15/+30/+60 min, et gère l'authentification des
utilisateurs.

## Stack

- **FastAPI** — API REST
- **Aurora / PostgreSQL** — comptes utilisateurs + historique des stations
- **S3 (Parquet)** — données silver (status des stations, prédictions ML)
- **Athena** — agrégations pour le dashboard
- **velhot-api-dev** — Lambda de l'équipe data, peut être utilisée comme
  source de données alternative (voir section dédiée)
- **JWT** — authentification, avec rôles `user` / `analyste` / `admin`

## Architecture des données

```
velhot-ingest-velov-dev  (Lambda, toutes les 5 min)
        │  écrit du JSON brut
        ▼
   S3 bronze (velhot-bronze-dev)
        │
        ▼  S3 trigger
velhot-transform-dev  (Lambda)
        │  nettoie, ajoute features temporelles, calcule fill_rate
        ▼
   S3 silver (velhot-silver-dev)
     ├── status/station_id={id}/date={YYYY-MM-DD}/data.parquet
     └── predictions/date={YYYY-MM-DD}/...   (écrit par velhot-train-model-dev)
        │
        ├──────────────┬─────────────────────┐
        ▼               ▼                     │
  CE BACKEND       velhot-api-dev              │
  (lecture S3       (Lambda équipe data,       │
   directe)          même cahier des charges)  │
        │               │                       │
        └───────┬───────┘                       │
                 ▼                               │
          Frontend / app mobile ◄────────────────┘
```

Ce backend peut récupérer les données de deux façons (voir `USE_LAMBDA_API`
ci-dessous) :

- **Lecture directe** S3 silver + Athena (`app/services/s3_service.py`,
  `athena_service.py`, `ml_service.py`)
- **Via la Lambda `velhot-api-dev`** de l'équipe data, qui fait le même
  travail (`app/services/lambda_api_client.py`, invocation par `boto3`)

Dans les deux cas, ce backend reste seul responsable de l'authentification
et de l'historique Aurora — `velhot-api-dev` n'a ni l'un ni l'autre.

## Endpoints

| Méthode | Route | Auth | Description |
|---------|-------|------|-------------|
| POST | `/auth/register` | public | Inscription (nom, prénom, email, password) |
| POST | `/auth/login` | public | Connexion → JWT |
| GET | `/auth/me` | user+ | Profil de l'utilisateur connecté |
| GET | `/stations` | user+ | Toutes les stations du jour |
| GET | `/stations/{id}` | user+ | Une station + prédictions ML |
| GET | `/predict?station_id=X` | user+ | Prédictions ML seules |
| GET | `/alerts` | user+ | Stations vides/pleines dans 30 min |
| GET | `/dashboard/peak-hours` | analyste+ | Fill-rate moyen par heure, 7 derniers jours |
| GET | `/dashboard/heatmap` | analyste+ | Fill-rate moyen par station aujourd'hui |
| GET | `/historique/{id}` | user+ | Historique Aurora (`?from=...&to=...`) |
| GET | `/` | public | Health check |

Documentation interactive : `http://localhost:8000/docs`
(cliquer "Authorize" et coller le token JWT brut, sans le préfixe `Bearer`).

## Démarrage local

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt --break-system-packages
cp .env.example .env   # voir section Configuration
uvicorn main:app --reload
```

### Base de données locale

```bash
sudo -u postgres createuser --superuser $USER
createdb velohot
```

Les tables (`utilisateurs`, `historique_stations`) sont créées
automatiquement au démarrage de l'API. `init_db.sql` est fourni comme
documentation / script manuel équivalent.

### Credentials AWS

Ne jamais mettre de clés AWS dans `.env`. Configurer via :

```bash
aws configure
```

boto3 lira automatiquement `~/.aws/credentials`. Sur AWS (ECS), un IAM Role
attaché au conteneur fournit les permissions sans configuration
supplémentaire.

## Configuration (`.env`)

```dotenv
DATABASE_URL=postgresql://<user>@/velohot?host=/var/run/postgresql
JWT_SECRET=<chaine_aleatoire_32+_chars>
JWT_EXPIRE_MINUTES=60

AWS_REGION=eu-west-3
S3_BUCKET_SILVER=velhot-silver-dev
S3_BUCKET_MODELS=velhot-models-dev

ATHENA_DATABASE=velohot_silver_dev
ATHENA_WORKGROUP=velohot-dev
ATHENA_OUTPUT_BUCKET=s3://velhot-athena-dev/

ENV=development
LOG_LEVEL=INFO
v
# true  -> récupère les données via boto3 lambda.invoke() sur velhot-api-dev
# false -> lecture directe S3/Athena (comportement historique)
USE_LAMBDA_API=true
```

Générer `JWT_SECRET` :
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | URL Aurora PostgreSQL (ou Postgres local) |
| `JWT_SECRET` | Clé secrète JWT (min 32 chars) |
| `JWT_EXPIRE_MINUTES` | Durée du token (défaut 60) |
| `AWS_REGION` | Région AWS |
| `S3_BUCKET_SILVER` | Bucket des données silver (status/, predictions/) |
| `S3_BUCKET_MODELS` | Bucket contenant `latest_model.txt` + modèles pickle |
| `ATHENA_DATABASE` | Base Athena interrogée pour `/dashboard/*` |
| `ATHENA_WORKGROUP` | Workgroup Athena |
| `ATHENA_OUTPUT_BUCKET` | Bucket de résultats Athena |
| `USE_LAMBDA_API` | `true` = données via `velhot-api-dev` (boto3 invoke) / `false` = lecture directe S3/Athena |
| `LOG_LEVEL` | Niveau de log (défaut INFO) |

## Mode `USE_LAMBDA_API`

Quand `USE_LAMBDA_API=true`, les endpoints `/stations`, `/stations/{id}`,
`/predict`, `/alerts`, `/dashboard/*` appellent `velhot-api-dev` via
`boto3.client('lambda').invoke()` au lieu de lire S3/Athena/le modèle
directement (voir `app/services/lambda_api_client.py`).

Nécessite la permission IAM `lambda:InvokeFunction` sur `velhot-api-dev`
pour l'identité utilisée (utilisateur en local, rôle ECS en prod).

L'auth JWT et l'historique Aurora fonctionnent à l'identique dans les deux
modes — seule la source des données métier change.

## Tests

```bash
pytest app/tests/ -v
```

23 tests — auth, stations/predict/alerts (S3 et ML mockés), dashboard
(rôles + cas d'erreur 503), historique. Tournent en SQLite mémoire, en
mode `USE_LAMBDA_API=false` mocké ; aucune connexion réelle à AWS ou
Aurora n'est nécessaire.

## Gestion d'erreurs

Si S3, Athena ou `velhot-api-dev` sont inaccessibles (credentials
manquants, bucket introuvable, timeout, modèle manquant, permission
IAM refusée...), l'API renvoie un **503** :

```json
{
  "detail": "Service temporairement indisponible (S3)",
  "source": "S3",
  "reason": "Credentials AWS non configurés"
}
```

`source` vaut `S3`, `Athena` ou `LambdaAPI` selon le composant en cause.

Si les préfixes S3 existent mais sont vides (pipeline pas encore exécuté),
les endpoints renvoient une réponse vide (`[]`) sans erreur.

## Logging

Logs structurés sur stdout, format texte, prêts pour CloudWatch
(`app/logging_config.py`). Niveau configurable via `LOG_LEVEL`.

## Docker

```bash
docker build -t velhhot-backend .
```

### Tester l'image en local

Le conteneur ne peut pas utiliser le socket Unix PostgreSQL de l'hôte
(`/var/run/postgresql/...`) — il faut une connexion TCP. Créer un
`.env.docker` à partir de `.env`, en changeant uniquement `DATABASE_URL` :

```dotenv
DATABASE_URL=postgresql://<user>:<password>@localhost:5432/velohot
```

(donner un mot de passe à l'utilisateur PostgreSQL local si besoin :
`sudo -u postgres psql -c "ALTER USER <user> WITH PASSWORD '<password>';"`)

Puis lancer (arrêter `uvicorn --reload` en local avant, le port 8000 est
sinon déjà occupé) :

```bash
docker run -p 8000:8000 --env-file .env.docker --network host velhhot-backend
```

Vérifier :
```bash
curl http://localhost:8000/
# {"status":"ok","version":"2.1.0"}
```

`--network host` n'est utile qu'en local pour atteindre PostgreSQL sur
l'hôte ; sur ECS la connexion à Aurora se fait nativement via le réseau
VPC, sans ce flag.

## Déploiement AWS

FastAPI tourne en conteneur Docker sur ECS Fargate à partir de l'image
buildée ci-dessus. L'IAM Role attaché au service ECS doit avoir :

- `s3:GetObject`, `s3:ListBucket` sur `velhot-silver-dev` et `velhot-models-dev`
- `athena:StartQueryExecution`, `athena:GetQueryResults`, `athena:GetQueryExecution`
- `lambda:InvokeFunction` sur `velhot-api-dev` (si `USE_LAMBDA_API=true`)
- accès réseau à Aurora PostgreSQL (security group)

`DATABASE_URL` doit pointer vers l'endpoint Aurora (variable d'environnement
ECS, via AWS Secrets Manager idéalement) au lieu de PostgreSQL local —
aucun autre changement n'est nécessaire dans le code ou l'image.

### Pousser l'image sur ECR (à faire côté infra)

```bash
aws ecr get-login-password --region eu-west-3 \
  | docker login --username AWS --password-stdin <account-id>.dkr.ecr.eu-west-3.amazonaws.com

docker tag velhhot-backend:latest \
  <account-id>.dkr.ecr.eu-west-3.amazonaws.com/velhhot-backend:latest

docker push <account-id>.dkr.ecr.eu-west-3.amazonaws.com/velhhot-backend:latest
```