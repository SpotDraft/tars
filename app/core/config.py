from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DEPLOYMENT_ENV: str = "DEV"
    LOG_LEVEL: str = "INFO"
    API_V1_STR: str = "/api/v1"


settings = Settings()
