# Geo-Prioridad Vulnerable

Plataforma geoespacial en desarrollo para apoyar la priorización de lugares sensibles y explorar la coordinación de emergencias en Sonsonate. La [propuesta de producto](PROPUESTA_PRODUCTO.md) describe una posible ampliación para integrar reportes de incidentes y verificación de rutas; esa necesidad local aún está pendiente de validación.

## Arquitectura y estado actual

- **Backend (`backend/`)**: FastAPI, SQLAlchemy asíncrono, GeoAlchemy2, Alembic y cliente de OpenStreetMap Overpass.
- **Base de datos**: PostgreSQL + PostGIS para guardar lugares geográficos y consultar proximidad.
- **Frontend (`frontend/`)**: Vue 3 + TypeScript + Pinia + Element Plus + Leaflet, integrado con el contrato OpenAPI.
- **Implementado**: ingesta de lugares sensibles, persistencia espacial, puntuación inicial, API REST y tablero de mapa/cola de atención.
- **Pendiente como ampliación**: reportes de incidentes, verificación de rutas por modo de desplazamiento, asignación de brigadas y alertas.

La puntuación actual ordena lugares de referencia; no calcula por sí sola la prioridad operativa de un desastre.

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
