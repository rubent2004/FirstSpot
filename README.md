# FirstSpot

Geospatial prioritization platform for humanitarian response, civil protection, and healthcare institutions to identify, classify, and prioritize critical locations with vulnerable population concentrations in El Salvador (starting with **Sonsonate**).

**FirstSpot** helps teams identify where to act first and coordinate what happens after an incident.

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

## Coordinación entre instituciones

FirstSpot now supports a public, place-centered activity log so responders can see **quién hizo qué, dónde y cuándo**:

1. An institution submits its name, country, sector, and a responsible contact. FirstSpot returns a `FSP-…` tracking code and leaves the request **pending**.
2. The tracking code is **not proof of identity**. A platform moderator must independently verify the institution through official channels before approving it.
3. Once verified, the institution owner can issue single-use invitations to colleagues. Every person uses an individual account; no shared “police” or “fire service” password is required.
4. Verified members can append actions such as “reported”, “unit en route”, “on scene”, “needs support”, and “resolved”, with an operational status, urgency, estimated population, and notes.
5. Anyone can read the public activity timeline for a place. It shows the responder’s display name and verified organization, but never exposes their account email. Activity entries cannot be edited or deleted through the API.

Anonymous edits to a place’s shared triage state are no longer allowed. The old triage endpoint now requires a bearer token from a verified organization and appends an audit entry atomically with the place update. Avoid patient names, health details, or other sensitive personal data in public notes.

The current map/priority snapshot still reflects the **latest submitted triage**, not a reconciled multi-agency consensus and not independently confirmed field truth. The activity timeline preserves each organization's own action so responders can compare reports and decide locally.

### Required backend secrets

Before using account login or moderation, set different random secrets in `backend/.env` (do not commit this file):

```bash
cd backend
cp .env.example .env
python - <<'PY'
from pathlib import Path
import secrets
p = Path('.env')
s = p.read_text()
s = s.replace('JWT_SECRET=""', f'JWT_SECRET="{secrets.token_hex(32)}"')
s = s.replace('PLATFORM_ADMIN_KEY=""', f'PLATFORM_ADMIN_KEY="{secrets.token_hex(32)}"')
p.write_text(s)
PY
```

The first value, `JWT_SECRET`, signs short-lived access tokens. The separate `PLATFORM_ADMIN_KEY` authorizes manual verification at `POST /api/v1/institutions/verification` via the `X-Platform-Admin-Key` header. A reviewer must validate the organization independently before using that endpoint. Do not put the moderator key in the frontend or expose it to applicants.

For a public deployment, also require HTTPS, configure a reverse-proxy rate limit on registration/login/moderation, protect and rotate secrets, back up the database, and establish a staffed verification and abuse-response process. This MVP does not yet include email/domain proof, password recovery, or distributed rate limiting.

## One-Command Quickstart (`just`)

The repository includes a root [`justfile`](file:///home/ruben/Documentos/PROYECTOS/RALLY_LATAM/geo-prioridad-vulnerable/justfile) to manage the entire stack:

```bash
# List all available commands
just --list

# Start everything in the background: PostGIS + migrations + FastAPI + Vue 3
just up2
# Open http://localhost:5173; check logs/status with `just status`, stop with `just down`
# The API health endpoint is checked first, so an already-running backend is reused.

# Optional: keep the servers attached to the terminal instead
just up

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

The backend exposes public registration/login and organization moderation under `/api/v1/institutions`; each place’s public coordination timeline is at `/api/v1/places/{place_id}/activities`. Full schemas are available at `/openapi.json` and `/docs`.
