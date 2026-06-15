from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str
    JWT_SECRET: str
    JWT_EXPIRE_MINUTES: int = 60
    AWS_REGION: str = "eu-west-3"
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    S3_BUCKET_SILVER: str = "velhhot-silver"
    ATHENA_DATABASE: str = "velhhot"
    ATHENA_OUTPUT_BUCKET: str = "s3://velhhot-athena-results/"
    ENV: str = "development"
    LOG_LEVEL: str = "INFO"

    class Config:
        env_file = ".env"


settings = Settings()
