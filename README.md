# Vél'hot Backend v2

FastAPI · Aurora PostgreSQL · S3 Parquet · Athena · JWT

## Endpoints

| Méthode | Route | Auth | Description |
|---------|-------|------|-------------|
| POST | `/auth/register` | public | Inscription (nom, prénom, email, password) |
| POST | `/auth/login` | public | Connexion → JWT |
| GET | `/stations` | user+ | Toutes les stations du jour (S3) |
| GET | `/stations/{id}` | user+ | Une station + prédictions ML |
| GET | `/predict?station_id=X` | user+ | Prédictions ML seules |
| GET | `/alerts` | user+ | Stations vides/pleines dans 30 min |
| GET | `/dashboard/peak-hours` | analyste+ | Fill-rate moyen par heure (Athena) |
| GET | `/dashboard/heatmap` | analyste+ | Fill-rate par station aujourd'hui (Athena) |
| GET | `/historique/{id}` | user+ | Historique Aurora (`?from=...&to=...`) |
| GET | `/` | public | Health check |

## Démarrage local

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # remplir les valeurs
uvicorn main:app --reload
# → http://localhost:8000/docs
```

## Variables d'environnement (.env)

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | URL Aurora PostgreSQL |
| `JWT_SECRET` | Clé secrète JWT (min 32 chars) |
| `JWT_EXPIRE_MINUTES` | Durée du token (défaut 60) |
| `AWS_REGION` | Région AWS (défaut eu-west-3) |
| `S3_BUCKET_SILVER` | Nom du bucket S3 silver |
| `ATHENA_DATABASE` | Base de données Athena |
| `ATHENA_OUTPUT_BUCKET` | Bucket pour les résultats Athena |

Générer JWT_SECRET :
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

## Sur AWS

FastAPI tourne dans un conteneur Docker sur ECS Fargate.
Les variables d'environnement sont injectées par Terraform via AWS Secrets Manager.
IAM Role ECS doit avoir : `s3:GetObject`, `s3:ListBucket`, `athena:StartQueryExecution`, `athena:GetQueryResults`.
