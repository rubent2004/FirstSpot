set dotenv-load := false
set shell := ["bash", "-cu"]

# List available task recipes
default:
    @just --list

# Start PostGIS container, wait for readiness, and apply Alembic migrations
db-up:
    #!/usr/bin/env bash
    set -euo pipefail
    docker compose up -d
    echo "Waiting for PostGIS container (geo-prioridad-postgis) to become ready..."
    for _ in {1..30}; do
        if docker exec geo-prioridad-postgis pg_isready -U postgres -d geo_prioridad >/dev/null 2>&1; then
            break
        fi
        sleep 1
    done
    uv run --directory backend alembic upgrade head

# Stop PostGIS container
db-down:
    docker compose down

# Run Alembic database migrations to latest head
migrate:
    uv run --directory backend alembic upgrade head

# Run FastAPI backend server on http://localhost:8000
backend:
    uv run --directory backend uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Run Vue 3 + Vite frontend server on http://localhost:5173
frontend:
    pnpm --dir frontend run dev --host 0.0.0.0 --port 5173

# Start the entire stack (PostGIS + FastAPI + Vue 3) in the foreground
up: db-up
    #!/usr/bin/env bash
    set -euo pipefail
    trap 'kill 0' INT TERM EXIT
    echo "Starting FastAPI backend (:8000) and Vue 3 frontend (:5173)..."
    uv run --directory backend uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 &
    pnpm --dir frontend run dev --host 0.0.0.0 --port 5173 &
    wait

# Start the entire stack (PostGIS + FastAPI + Vue 3) in the background with logs in .logs/
up-bg: db-up
    #!/usr/bin/env bash
    set -euo pipefail
    mkdir -p .logs
    if [[ -f .logs/backend.pid ]] && kill -0 "$(<.logs/backend.pid)" 2>/dev/null; then
        echo "Backend already running (PID $(<.logs/backend.pid))"
    else
        nohup uv run --directory backend uvicorn app.main:app --host 0.0.0.0 --port 8000 > .logs/backend.log 2>&1 &
        echo $! > .logs/backend.pid
        echo "Started Backend in background (PID $(<.logs/backend.pid)) -> http://localhost:8000"
    fi
    if [[ -f .logs/frontend.pid ]] && kill -0 "$(<.logs/frontend.pid)" 2>/dev/null; then
        echo "Frontend already running (PID $(<.logs/frontend.pid))"
    else
        nohup pnpm --dir frontend run dev --host 0.0.0.0 --port 5173 > .logs/frontend.log 2>&1 &
        echo $! > .logs/frontend.pid
        echo "Started Frontend in background (PID $(<.logs/frontend.pid)) -> http://localhost:5173"
    fi

# Stop background Backend/Frontend processes and shut down PostGIS container
down:
    #!/usr/bin/env bash
    set -euo pipefail
    for service in backend frontend; do
        pid_file=".logs/${service}.pid"
        if [[ -f "${pid_file}" ]]; then
            pid="$(<"${pid_file}")"
            if kill -0 "${pid}" 2>/dev/null; then
                kill "${pid}" 2>/dev/null || true
                echo "Stopped ${service} (PID ${pid})"
            fi
            rm -f "${pid_file}"
        fi
    done
    docker compose down

# Export OpenAPI 3.1 schema from FastAPI and generate TypeScript SDK in frontend/
codegen:
    uv run --directory backend python -c "import json; from pathlib import Path; from app.main import app; Path('openapi.json').write_text(json.dumps(app.openapi(), indent=2) + '\n', encoding='utf-8')"
    pnpm --dir frontend run generate:api

# Synchronize a predefined El Salvador zone (e.g. sonsonate, san_salvador) into PostGIS
sync zone="sonsonate": db-up
    #!/usr/bin/env bash
    set -euo pipefail
    uv run --directory backend python - "{{zone}}" <<'PY'
    import asyncio
    import sys
    from app.core.database import async_session_factory
    from app.modules.ingestion.infrastructure.overpass_client import OverpassHttpClient
    from app.modules.places.infrastructure.router import SyncZoneRequest, sync_places_from_overpass

    async def main(zone_key: str) -> None:
        req = SyncZoneRequest(zone_key=zone_key)
        async with async_session_factory() as session:
            res = await sync_places_from_overpass(
                req,
                session,
                OverpassHttpClient(timeout_seconds=12.0),
            )
            print(
                f"Synced zone={res.zone_name}: {res.synced_places_count} places "
                f"(used_fallback={res.used_fallback}, source={res.source_endpoint})"
            )

    asyncio.run(main(sys.argv[1]))
    PY

# Run full verification suite (PostGIS + Backend pytest + Frontend Vitest + TypeScript build)
test: db-up
    uv run --directory backend pytest -v
    pnpm --dir frontend run test
    pnpm --dir frontend run build

# Check status of PostGIS container, database records, and active dev ports
status:
    #!/usr/bin/env bash
    set -euo pipefail
    echo "=== Docker PostGIS Status ==="
    docker compose ps
    echo ""
    echo "=== PostGIS vulnerable_places Count ==="
    docker exec geo-prioridad-postgis psql -U postgres -d geo_prioridad -tAc "SELECT zone_name, COUNT(*) AS places_count, ROUND(AVG(priority_score)::numeric, 2) AS avg_score FROM vulnerable_places GROUP BY zone_name ORDER BY places_count DESC;" || true
    echo ""
    echo "=== Background Dev Processes ==="
    for service in backend frontend; do
        pid_file=".logs/${service}.pid"
        if [[ -f "${pid_file}" ]] && kill -0 "$(<"${pid_file}")" 2>/dev/null; then
            echo "${service}: RUNNING (PID $(<"${pid_file}"))"
        else
            echo "${service}: NOT RUNNING (background)"
        fi
    done
