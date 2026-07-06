from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DEPLOYMENT_ENV: str = "DEV"
    LOG_LEVEL: str = "INFO"
    API_V1_STR: str = "/api/v1"

    # Postgres — async DSN (asyncpg driver)
    # Format: postgresql+asyncpg://user:password@host:port/dbname
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/tars"

    # Used as the default value for domain_setting.default_domain
    CLUSTER_ID: str = "IN"


settings = Settings()
