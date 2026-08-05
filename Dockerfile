# Base image: python:3.12-slim is the standard across all SpotDraft FastAPI services
# (oogway, neo-sites-gateway, tigress, kratos, mission-control-backend).
#
# Chainguard migration note: django-rest-api uses a SpotDraft-published sanctioned
# builder (ghcr.io/spotdraft/python-builder) backed by cgr.dev/chainguard-private/python:3.12-dev
# with SafeDep PMG malware scanning. This is worth adopting for Tars too, but requires
# the platform/security team to publish a runner image for this service first.
# Track as a follow-up ticket.
FROM --platform=linux/amd64 us-central1-docker.pkg.dev/spotdraft-qa/sd-us-chainguard/python-fips:3.12

# Prevent .pyc files, enable unbuffered stdout — standard across all SpotDraft FastAPI services
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_NO_DEV=1 \
    UV_PYTHON_DOWNLOADS=0

WORKDIR /app

# Copy uv binary from its official image (pattern used in neo-sites-gateway, oogway)
COPY --from=ghcr.io/astral-sh/uv:0.10.6 /uv /uvx /bin/

# Install deps first (layer cached until pyproject.toml or uv.lock changes)
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-install-project

# Copy application code
COPY app ./app

EXPOSE 8000

CMD ["/app/.venv/bin/uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
