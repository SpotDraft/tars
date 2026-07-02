import logging
from typing import Any, ClassVar

from pydantic_settings import BaseSettings, SettingsConfigDict
from pythonjsonlogger import json as json_logger


class GcpJsonFormatter(json_logger.JsonFormatter):
    """Adds 'severity' field so GCP Log Explorer reads log levels correctly.

    GKE's logging agent maps the JSON 'severity' key to the log entry severity.
    Without it, all logs appear as INFO in Cloud Logging regardless of level.
    Pattern copied from oogway/app/core/config.py.
    """

    def add_fields(
        self,
        log_data: dict[str, Any],
        record: logging.LogRecord,
        message_dict: dict[str, Any],
    ) -> None:
        super().add_fields(log_data, record, message_dict)
        log_data["severity"] = record.levelname


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DEPLOYMENT_ENV: str = "DEV"
    LOG_LEVEL: str = "INFO"
    API_V1_STR: str = "/api/v1"


settings = Settings()


class LoggingConfig:
    """dictConfig-compatible structured logging. Pattern from oogway/neo-sites-gateway."""

    version = 1
    disable_existing_loggers = False
    formatters: ClassVar[dict] = {
        "json": {
            "()": "app.core.config.GcpJsonFormatter",
            "fmt": "%(asctime)s %(levelname).4s %(name)-12s %(message)s",
        },
    }
    handlers: ClassVar[dict] = {
        "console": {
            "formatter": "json",
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stdout",
        },
    }
    loggers: ClassVar[dict] = {
        "uvicorn.access": {"handlers": ["console"], "level": settings.LOG_LEVEL},
        "": {"handlers": ["console"], "level": settings.LOG_LEVEL},
    }

    @classmethod
    def to_dict(cls) -> dict:
        return {
            "version": cls.version,
            "disable_existing_loggers": cls.disable_existing_loggers,
            "formatters": cls.formatters,
            "handlers": cls.handlers,
            "loggers": cls.loggers,
        }
