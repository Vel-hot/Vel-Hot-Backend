from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str
    JWT_SECRET: str
    JWT_EXPIRE_MINUTES: int = 60

    AWS_REGION: str = "eu-west-3"
    S3_BUCKET_SILVER: str = "velhot-silver-dev"
    S3_BUCKET_MODELS: str = "velhot-models-dev"

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

    class Config:
        env_file = ".env"


settings = Settings()