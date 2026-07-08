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
│   │   ├── postgres.py              # SQLAlchemy engine, session factory, base ORM classes
│   │   ├── models.py                # All ORM model definitions (centralised)
│   │   ├── enums.py                 # Shared DB enums
│   │   └── firestore.py             # Firestore client (stub)
│   ├── agreement/                   # Agreement bounded context
│   │   ├── data/postgres/           # Repository layer
│   │   ├── domain/use_cases/        # Business logic
│   │   └── presentation/            # Routes / request handlers
│   ├── clickwrap/                   # Clickwrap bounded context
│   │   ├── data/postgres/
│   │   ├── domain/use_cases/
│   │   └── presentation/
│   ├── consent/                     # Consent bounded context (Firestore-backed)
│   │   ├── data/firestore/
│   │   ├── domain/use_cases/
│   │   └── presentation/
│   └── legal_hub/                   # Legal hub bounded context
│       ├── data/postgres/
│       ├── domain/use_cases/
│       └── presentation/
├── alembic/                         # DB migrations
│   ├── env.py
│   └── versions/
├── tests/
│   ├── test_health.py
│   ├── agreement/
│   ├── clickwrap/
│   ├── consent/
│   └── legal_hub/
├── alembic.ini
├── Dockerfile
├── pyproject.toml
├── ruff.toml
├── bors.toml
└── .env.example
```

---

## Local Setup

### Prerequisites

- **[uv](https://docs.astral.sh/uv/)** — Python package manager. Install once with:
  ```bash
  curl -LsSf https://astral.sh/uv/install.sh | sh
  ```

- **PostgreSQL** — the service uses Postgres for control-plane data. A local instance is required. With Homebrew:
  ```bash
  brew install postgresql@16
  brew services start postgresql@16
  ```

### 1. Install dependencies

```bash
uv python install 3.12
uv sync
```

### 2. Configure environment variables

```bash
cp .env.example .env
```

Open `.env` and set at minimum:

```bash
DEPLOYMENT_ENV=DEV
LOG_LEVEL=INFO
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/tars
```

See the [Environment Variables](#environment-variables) section for all options.

### 3. Create the database

```bash
psql -U postgres -c "CREATE DATABASE tars;"
```

### 4. Apply migrations

```bash
uv run alembic upgrade head
```

### 5. Start the dev server

```bash
uv run uvicorn app.main:app --reload
```

The service is available at:
- `http://127.0.0.1:8000/ht` — health check (Kubernetes liveness/readiness probe)
- `http://127.0.0.1:8000/docs` — Swagger UI

---

## Database Migrations

Migrations are managed with [Alembic](https://alembic.sqlalchemy.org/). The `DATABASE_URL` is read from `.env` (or the environment) — it is not set in `alembic.ini`.

### Apply all pending migrations

```bash
uv run alembic upgrade head
```

### Roll back the latest migration

```bash
uv run alembic downgrade -1
```

### Check current migration state

```bash
uv run alembic current
```

### View migration history

```bash
uv run alembic history --verbose
```

### Create a new migration

After adding or modifying an ORM model in `app/db/models.py`, autogenerate a migration:

```bash
uv run alembic revision --autogenerate -m "short_description_of_change"
```

Always review the generated file in `alembic/versions/` before committing — autogenerate can miss certain changes (e.g. check constraints, custom indexes, server defaults).

> **Note:** Migration PRs must be kept separate from feature code changes. See the team PR guidelines.

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

All variables are read by `app/core/config.py` via pydantic-settings. Set them in `.env` locally or as real environment variables in deployed environments. Real environment variables take precedence over `.env`.

| Variable | Default | Description |
|---|---|---|
| `DEPLOYMENT_ENV` | `DEV` | Deployment environment label (`DEV`, `QA`, `PROD`). Enables SQL echo logging when set to `DEV`. |
| `LOG_LEVEL` | `INFO` | Python log level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `API_V1_STR` | `/api/v1` | API version prefix |
| `DATABASE_URL` | `postgresql+asyncpg://postgres:postgres@localhost:5432/tars` | Async DSN for Postgres. Format: `postgresql+asyncpg://user:password@host:port/dbname` |
| `CLUSTER_ID` | `IN` | Cluster identifier. Used as the subdomain component in `domain_setting.default_domain` (e.g. `clickwrap.IN.spotdraft.com`) |

---

## Architecture

Tars follows a **domain-driven, layered architecture** consistent with other SpotDraft FastAPI services:

```
presentation/   ← FastAPI routes, request/response handling
domain/         ← Business logic (use cases, domain models)
  use_cases/
data/           ← Persistence adapters (Postgres or Firestore)
```

Each bounded context (`agreement`, `clickwrap`, `consent`, `legal_hub`) owns its full stack of layers independently. Cross-cutting concerns (config, logging, DB sessions) live in `app/core/` and `app/db/`.

**ORM models** are centralised in `app/db/models.py` rather than per-module files — this avoids circular imports and keeps the migration target (`Base.metadata`) in one place.

**Storage:**
- `agreement`, `clickwrap`, `legal_hub` — PostgreSQL via async SQLAlchemy (`app/db/postgres.py`)
- `consent` — Firestore via `app/db/firestore.py`

---

## Docker

```bash
docker build -t tars .
docker run -p 8000:8000 --env-file .env tars
```

Base image: `python:3.12-slim`.

---

## Branching & Deployment

| Branch | Purpose |
|---|---|
| `master` | Integration branch — always deployable to DEV |
| `feat/*` | Feature branches; PR → bors → master |
| `release-YYYYMMDD` | Release snapshot; tagged `qa_YYYYMMDD` for QA deploy |

Deployments target Kubernetes clusters via Argo CD (gitops repo). The `/ht` endpoint maps to Kubernetes liveness and readiness probes.
