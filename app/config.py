import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str
    JWT_SECRET: str
    JWT_EXPIRE_MINUTES: int = 60

    AWS_REGION: str = "eu-west-3"
    S3_BUCKET_SILVER: str = "velhot-silver-dev"
    S3_BUCKET_MODELS: str = "velhot-models-dev"

    AWS_ACCESS_KEY_ID: str | None = None
    AWS_SECRET_ACCESS_KEY: str | None = None

    ATHENA_DATABASE: str = "velohot_silver_dev"
    ATHENA_WORKGROUP: str = "velohot-dev"
    ATHENA_OUTPUT_BUCKET: str = "s3://velhot-athena-dev/"

    # --- Lambda velhot-api-dev (équipe data) -----------------------------
    # USE_LAMBDA_API=true  -> les données (stations/predict/alerts/dashboard)
    #                         sont récupérées via boto3 lambda.invoke()
    #                         sur velhot-api-dev, au lieu d'une lecture
    #                         directe S3/Athena.
    # USE_LAMBDA_API=false -> comportement par défaut (lecture directe).
    # Nécessite la permission IAM lambda:InvokeFunction sur velhot-api-dev.
    USE_LAMBDA_API: bool = False

    ENV: str = "development"
    LOG_LEVEL: str = "INFO"
    STATIONS_CACHE_TTL: int = 3600 # 1 heure

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()

if settings.AWS_ACCESS_KEY_ID:
    os.environ["AWS_ACCESS_KEY_ID"] = settings.AWS_ACCESS_KEY_ID
if settings.AWS_SECRET_ACCESS_KEY:
    os.environ["AWS_SECRET_ACCESS_KEY"] = settings.AWS_SECRET_ACCESS_KEY