# Tars

FastAPI microservice for clickwrap consent management at SpotDraft.

---

## Folder Structure

```
tars/
├── app/
│   ├── main.py                      # FastAPI app factory, lifespan, /ht health check
│   ├── core/
│   │   ├── config.py                # pydantic-settings Settings (env vars)
│   │   └── log_config.py            # GCP-compatible JSON logging (GcpJsonFormatter)
│   ├── db/
│   │   ├── postgres.py              # PostgreSQL session/engine (stub)
│   │   └── firestore.py             # Firestore client (stub)
│   ├── agreement/                   # Agreement bounded context
│   │   ├── models.py
│   │   ├── data/postgres/           # Repository layer
│   │   ├── domain/use_cases/        # Business logic
│   │   └── presentation/            # Routes / request handlers
│   ├── clickwrap/                   # Clickwrap bounded context
│   │   ├── models.py
│   │   ├── data/postgres/
│   │   ├── domain/use_cases/
│   │   └── presentation/
│   ├── consent/                     # Consent bounded context (Firestore-backed)
│   │   ├── data/firestore/
│   │   ├── domain/use_cases/
│   │   └── presentation/
│   └── legal_hub/                   # Legal hub bounded context
│       ├── models.py
│       ├── data/postgres/
│       ├── domain/use_cases/
│       └── presentation/
├── tests/
│   ├── test_health.py
│   ├── agreement/
│   ├── clickwrap/
│   ├── consent/
│   └── legal_hub/
├── Dockerfile
├── pyproject.toml
├── ruff.toml
├── bors.toml
└── .env.example
```

---

## Local Setup

### Prerequisites

- [UV](https://docs.astral.sh/uv/) — install once with:
  ```bash
  curl -LsSf https://astral.sh/uv/install.sh | sh
  ```

### Install & Run

```bash
# 1. Install Python 3.12 and project dependencies
uv python install 3.12
uv sync

# 2. Copy and configure environment variables
cp .env.example .env
# Edit .env as needed

# 3. Start the dev server (hot-reload)
uv run uvicorn app.main:app --reload
```

The service will be available at:
- `http://127.0.0.1:8000/ht` — health check (Kubernetes liveness/readiness probe)
- `http://127.0.0.1:8000/docs` — Swagger UI

---

## Running Tests

```bash
uv run pytest
```

---

## Linting & Formatting

```bash
uv run ruff check .       # lint
uv run ruff format .      # format
```

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `DEPLOYMENT_ENV` | `DEV` | Deployment environment label (`DEV`, `QA`, `PROD`) |
| `LOG_LEVEL` | `INFO` | Python log level |
| `API_V1_STR` | `/api/v1` | API version prefix |

---

## Architecture

Tars follows a **domain-driven, layered architecture** consistent with other SpotDraft FastAPI services (oogway, tigress):

```
presentation/   ← FastAPI routes, request/response handling
domain/         ← Business logic (use cases, domain models)
  use_cases/
data/           ← Persistence adapters (Postgres or Firestore)
models.py       ← SQLAlchemy / Pydantic domain models
```

Each bounded context (`agreement`, `clickwrap`, `consent`, `legal_hub`) owns its full stack of layers independently. Cross-cutting concerns (config, logging, DB sessions) live in `app/core/` and `app/db/`.

**Storage:**
- `agreement`, `clickwrap`, `legal_hub` — PostgreSQL via `app/db/postgres.py`
- `consent` — Firestore via `app/db/firestore.py`

---

## Docker

```bash
docker build -t tars .
docker run -p 8000:8000 --env-file .env tars
```

Base image: `python:3.12-slim` (standard across SpotDraft FastAPI services).

> **Chainguard migration:** django-rest-api uses `ghcr.io/spotdraft/python-builder` (backed by `cgr.dev/chainguard-private/python:3.12-dev` with SafeDep PMG). Adopting this for Tars is tracked as a follow-up once the platform team publishes a runner image.

---

## Branching & Deployment

| Branch | Purpose |
|---|---|
| `master` | Integration branch — always deployable to DEV |
| `feat/*` | Feature branches; PR → bors → master |
| `release-YYYYMMDD` | Release snapshot; tagged `qa_YYYYMMDD` for QA deploy |

Deployments target Kubernetes clusters via Argo CD (gitops repo). The `/ht` endpoint maps to Kubernetes liveness and readiness probes.
