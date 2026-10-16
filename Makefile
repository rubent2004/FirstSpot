SHELL := bash
.SHELLFLAGS := -euo pipefail -c
.DEFAULT_GOAL := help

.PHONY: help db-up db-down migrate backend frontend up up-bg down codegen sync test status

help:
	@echo "Comandos disponibles:"
	@echo "  make up          - Levanta PostGIS, backend (:8000) y frontend (:5173)"
	@echo "  make up-bg       - Levanta todo en segundo plano con logs en .logs/"
	@echo "  make down        - Detiene backend, frontend y el contenedor PostGIS"
	@echo "  make db-up       - Levanta el contenedor PostGIS y aplica migraciones"
	@echo "  make db-down     - Detiene el contenedor PostGIS"
	@echo "  make migrate     - Aplica migraciones Alembic"
	@echo "  make backend     - Inicia el servidor backend FastAPI"
	@echo "  make frontend    - Inicia el servidor frontend Vue 3"
	@echo "  make sync        - Sincroniza lugares (ej: make sync ZONE=sonsonate)"
	@echo "  make codegen     - Exporta esquema OpenAPI y regenera cliente TypeScript"
	@echo "  make test        - Ejecuta tests de backend, frontend y compilación"
	@echo "  make status      - Muestra el estado de contenedores y servicios"

db-up:
	docker compose up -d
	@echo "Waiting for PostGIS container (geo-prioridad-postgis) to become ready..."
	@for _ in {1..30}; do \
		if docker exec geo-prioridad-postgis pg_isready -U postgres -d geo_prioridad >/dev/null 2>&1; then \
			break; \
		fi; \
		sleep 1; \
	done
	uv run --directory backend alembic upgrade head

db-down:
	docker compose down

migrate:
	uv run --directory backend alembic upgrade head

backend:
	uv run --directory backend uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

frontend:
	pnpm --dir frontend run dev --host 0.0.0.0 --port 5173

up: db-up
	@echo "Starting FastAPI backend (:8000) and Vue 3 frontend (:5173)..."
	trap 'kill 0' INT TERM EXIT; \
	uv run --directory backend uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 & \
	pnpm --dir frontend run dev --host 0.0.0.0 --port 5173 & \
	wait

up-bg: db-up
	@mkdir -p .logs
	@if [ -f .logs/backend.pid ] && kill -0 "$$(cat .logs/backend.pid)" 2>/dev/null; then \
		echo "Backend already running (PID $$(cat .logs/backend.pid))"; \
	else \
		nohup uv run --directory backend uvicorn app.main:app --host 0.0.0.0 --port 8000 > .logs/backend.log 2>&1 & \
		echo $$! > .logs/backend.pid; \
		echo "Started Backend in background (PID $$(cat .logs/backend.pid)) -> http://localhost:8000"; \
	fi
	@if [ -f .logs/frontend.pid ] && kill -0 "$$(cat .logs/frontend.pid)" 2>/dev/null; then \
		echo "Frontend already running (PID $$(cat .logs/frontend.pid))"; \
	else \
		nohup pnpm --dir frontend run dev --host 0.0.0.0 --port 5173 > .logs/frontend.log 2>&1 & \
		echo $$! > .logs/frontend.pid; \
		echo "Started Frontend in background (PID $$(cat .logs/frontend.pid)) -> http://localhost:5173"; \
	fi

down:
	@for service in backend frontend; do \
		pid_file=".logs/$${service}.pid"; \
		if [ -f "$${pid_file}" ]; then \
			pid="$$(cat "$${pid_file}")"; \
			if kill -0 "$${pid}" 2>/dev/null; then \
				kill "$${pid}" 2>/dev/null || true; \
				echo "Stopped $${service} (PID $${pid})"; \
			fi; \
			rm -f "$${pid_file}"; \
		fi; \
	done
	docker compose down

codegen:
	uv run --directory backend python -c "import json; from pathlib import Path; from app.main import app; Path('openapi.json').write_text(json.dumps(app.openapi(), indent=2) + '\n', encoding='utf-8')"
	pnpm --dir frontend run generate:api

ZONE ?= sonsonate

sync: db-up
	uv run --directory backend python -m app.sync_cli $(ZONE)

test: db-up
	uv run --directory backend pytest -v
	pnpm --dir frontend run test
	pnpm --dir frontend run build

status:
	@echo "=== Docker PostGIS Status ==="
	@docker compose ps
	@echo ""
	@echo "=== PostGIS vulnerable_places Count ==="
	@docker exec geo-prioridad-postgis psql -U postgres -d geo_prioridad -tAc "SELECT zone_name, COUNT(*) AS places_count, ROUND(AVG(priority_score)::numeric, 2) AS avg_score FROM vulnerable_places GROUP BY zone_name ORDER BY places_count DESC;" || true
	@echo ""
	@echo "=== Background Dev Processes ==="
	@for service in backend frontend; do \
		pid_file=".logs/$${service}.pid"; \
		if [ -f "$${pid_file}" ] && kill -0 "$$(cat "$${pid_file}")" 2>/dev/null; then \
			echo "$${service}: RUNNING (PID $$(cat "$${pid_file}"))"; \
		else \
			echo "$${service}: NOT RUNNING (background)"; \
		fi; \
	done
