# Geo-Prioridad Vulnerable

Geospatial prioritization platform for humanitarian response, civil protection, and healthcare institutions to identify, classify, and prioritize critical locations with vulnerable population concentrations.

## Architecture Overview

- **Backend**: FastAPI (Hexagonal + Screaming Architecture), SQLAlchemy 2.0 (async), GeoAlchemy2, Shapely, Alembic.
- **Database**: PostgreSQL 16 + PostGIS 3.4 (`GEOGRAPHY(Point, 4326)` with `GIST` indexing).
- **External Data**: OpenStreetMap via Overpass API (`nwr` queries).
- **Frontend**: Vue 3 + TypeScript + Element Plus + Leaflet (`leaflet.heat`), typed via OpenAPI 3.1 contract (`@hey-api/openapi-ts`).

## Phase 1 Quickstart

### 1. Start Spatial Database (PostGIS)

```bash
docker compose up -d
docker compose ps
```

By default, PostgreSQL + PostGIS listens on host port `5434` (`localhost:5434`).

### 2. Backend Setup & Migrations

```bash
cd backend
cp .env.example .env
uv sync
uv run alembic upgrade head
```

### 3. Run Tests & Development Server

```bash
cd backend
uv run pytest -v
uv run uvicorn app.main:app --reload --port 8000
```
