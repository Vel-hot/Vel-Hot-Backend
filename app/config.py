from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Base de données
    DATABASE_URL: str = "postgresql://velohot_admin:password@localhost:5432/velohot_silver"
    DATABASE_GOLD_URL: str = "postgresql://velohot_admin:password@localhost:5432/velohot_gold"

    # AWS (utilisé plus tard pour S3 / SageMaker)
    AWS_REGION: str = "eu-west-3"
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""

    # Environnement
    ENV: str = "development"   # "development" | "production"
    DEBUG: bool = True

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
