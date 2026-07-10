import logging
from contextlib import asynccontextmanager
from logging.config import dictConfig

from fastapi import FastAPI
from fastapi.middleware.gzip import GZipMiddleware

from app.clickwrap.presentation.router import router as clickwrap_router
from app.core.config import settings
from app.core.hmac_auth import AdminHMACMiddleware
from app.core.log_config import LoggingConfig

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

# Last added = outermost. HMAC must wrap GZip so it sees the raw request body.
app.add_middleware(GZipMiddleware)
app.add_middleware(AdminHMACMiddleware)
app.include_router(clickwrap_router)


@app.get("/ht", tags=["ops"])
async def health_check() -> dict[str, str]:
    """Health check endpoint used by Kubernetes liveness and readiness probes."""
    return {"status": "ok"}
