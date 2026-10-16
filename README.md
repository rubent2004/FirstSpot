# Geo-Prioridad Vulnerable

Geospatial prioritization platform for humanitarian response, civil protection, and healthcare institutions to identify, classify, and prioritize critical locations with vulnerable population concentrations in El Salvador (starting with **Sonsonate**).

## Architecture Overview

- **Backend (`backend/`)**: FastAPI (Hexagonal + Screaming Architecture), SQLAlchemy 2.0 (`AsyncSession`), GeoAlchemy2, Shapely, Alembic, `httpx` Overpass QL client (`nwr` + `[timeout:60]` + mirror failover + offline seed fallback).
- **Spatial Database (`docker-compose.yml`)**: PostgreSQL 16 + PostGIS 3.4 (`GEOGRAPHY(Point, 4326)` with `GIST` spatial index and `ST_DWithin` 500m cluster density calculation).
- **Contract-First Integration**: FastAPI exports an **OpenAPI 3.1** specification (`backend/openapi.json`) consumed by the frontend code generator (`pnpm run generate:api`) to produce `frontend/src/api/generated/`.
- **Frontend (`frontend/`)**: Vue 3 (`<script setup lang="ts">`) + TypeScript + Pinia + Element Plus + Leaflet (`leaflet.heat`) structured with Container/Presentational boundaries.

## Multi-Criteria Priority Formula

$$
\text{priority\_score} = \left( W_{\text{cat}} \times M_{\text{urg}} \right) + \left( 15 \times \ln(1 + P_{\text{vuln}}) \right) + \left( 5 \times N_{\text{500m}} \right)
$$

When `attention_status == "attended"`, the score is attenuated to `20%` (`0.2 * base_score`) so active emergency hotspots stand out on the heatmap.

## One-Command Quickstart (`just`)

The repository includes a root [`justfile`](file:///home/ruben/Documentos/PROYECTOS/RALLY_LATAM/geo-prioridad-vulnerable/justfile) to manage the entire stack:

```bash
# List all available commands
just --list

# Start PostGIS + apply migrations + launch FastAPI (:8000) & Vue 3 (:5173)
just up

# Or launch the full stack in the background (.logs/)
just up-bg

# Seed or refresh a zone from Overpass API (defaults to sonsonate)
just sync sonsonate

# Regenerate OpenAPI 3.1 schema and TypeScript SDK
just codegen

# Run full verification suite (PostGIS + pytest + Vitest + vue-tsc/vite build)
just test

# Check container, database counts, and process status
just status

# Stop background services and PostGIS container
just down
```

## Manual Step-by-Step Setup

### 1. Start Spatial Database (PostGIS)

```bash
docker compose up -d
docker compose ps
```

PostgreSQL 16 + PostGIS 3.4 listens on host port `5434` (`localhost:5434`).

### 2. Backend Setup, Migrations & Server

```bash
cd backend
cp .env.example .env
uv sync
uv run alembic upgrade head
uv run pytest -v
uv run uvicorn app.main:app --reload --port 8000
```

### 3. Frontend Setup, OpenAPI SDK Generation & Dev Server

```bash
cd frontend
pnpm install
pnpm run generate:api
pnpm run test
pnpm run dev
```

Open `http://localhost:5173` in your browser. On startup, the dashboard automatically loads (or synchronizes) **Sonsonate** vulnerable locations, renders the weighted heatmap and markers, and enables institutional triage dispatch.
