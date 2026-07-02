import logging
from contextlib import asynccontextmanager
from logging.config import dictConfig

from fastapi import FastAPI
from fastapi.middleware.gzip import GZipMiddleware

from app.core.config import LoggingConfig, settings

dictConfig(LoggingConfig.to_dict())
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    logger.info("tars starting", extra={"env": settings.DEPLOYMENT_ENV})
    yield
    logger.info("tars shutting down")


app = FastAPI(
    title="tars",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(GZipMiddleware)


@app.get("/ht", tags=["ops"])
async def health_check() -> dict[str, str]:
    """Health check endpoint used by Kubernetes liveness and readiness probes."""
    return {"status": "ok"}
