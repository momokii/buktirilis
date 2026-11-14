SHELL := /bin/bash
BACKEND := backend
VENV := $(BACKEND)/.venv
PY := $(VENV)/bin/python

# Local configuration is read from the gitignored .env file (copy .env.example).
# A missing BUKTIRILIS_SECRET_KEY fails closed when the app starts.
-include .env
APP_ENV ?= development
DATABASE_URL ?= postgresql+psycopg://buktirilis:buktirilis-dev-only@127.0.0.1:55432/buktirilis
ARTIFACT_ROOT ?= ./var/artifacts
STRIX_RUNS_ROOT ?= ./var/strix_runs
ALLOW_LOOPBACK_LAB_TARGETS ?= true
DEMO_SEED_ENABLED ?= true
LAB_BASE_URL ?= http://127.0.0.1:8099
PUBLIC_ORIGIN ?= http://127.0.0.1:5173

export

.PHONY: help install db lab api worker web dev test lint typecheck check demo seed migrate compose-config clean

help:
	@echo "BuktiRilis targets"
	@echo "  make install     install backend (uv) and web (npm) dependencies"
	@echo "  make db          start the local PostgreSQL container"
	@echo "  make lab         run the synthetic staging lab on 127.0.0.1:8099"
	@echo "  make api         run the API on 127.0.0.1:8000"
	@echo "  make worker      run the job worker"
	@echo "  make web         run the Vite dev server on 127.0.0.1:5173"
	@echo "  make dev         run lab + api + worker + web together (foreground)"
	@echo "  make migrate     apply database migrations"
	@echo "  make seed        create the demo project and runs (needs lab + db)"
	@echo "  make demo        migrate, seed, and print the demo credentials path"
	@echo "  make test        backend test suite"
	@echo "  make lint        ruff lint + format check"
	@echo "  make typecheck   mypy"
	@echo "  make check       lint + typecheck + backend tests + web build"

install:
	cd $(BACKEND) && uv sync
	cd web && npm ci

db:
	docker start buktirilis-db-dev >/dev/null 2>&1 || \
	docker run -d --name buktirilis-db-dev \
		-e POSTGRES_USER=buktirilis \
		-e POSTGRES_PASSWORD=buktirilis-dev-only \
		-e POSTGRES_DB=buktirilis \
		-p 127.0.0.1:55432:5432 postgres:16-alpine
	@sleep 2
	@docker exec buktirilis-db-dev pg_isready -U buktirilis

migrate: db
	cd $(BACKEND) && $(PY) -m alembic upgrade head

seed: migrate
	cd $(BACKEND) && $(PY) -m app.cli seed-demo

demo: seed
	@echo "Demo credentials: $(CURDIR)/var/demo-credentials.txt"

lab:
	cd lab && $(CURDIR)/$(PY) -m uvicorn app.main:APP --host 127.0.0.1 --port 8099

api:
	cd $(BACKEND) && $(PY) -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

worker:
	cd $(BACKEND) && $(PY) -m app.worker

web:
	cd web && npm run dev -- --host 127.0.0.1 --port 5173

dev:
	@echo "Starting lab, api, worker, and web. Ctrl-C stops all."
	@trap 'kill 0' INT TERM; \
	( cd lab && $(CURDIR)/$(PY) -m uvicorn app.main:APP --host 127.0.0.1 --port 8099 ) & \
	( cd $(BACKEND) && $(PY) -m uvicorn app.main:app --host 127.0.0.1 --port 8000 ) & \
	( cd $(BACKEND) && $(PY) -m app.worker ) & \
	( cd web && npm run dev -- --host 127.0.0.1 --port 5173 ) & \
	wait

test:
	cd $(BACKEND) && $(PY) -m pytest

lint:
	cd $(BACKEND) && .venv/bin/ruff check app tests && .venv/bin/ruff format --check app tests

format:
	cd $(BACKEND) && .venv/bin/ruff format app tests

typecheck:
	cd $(BACKEND) && .venv/bin/mypy app

check: lint typecheck test
	cd web && npm run typecheck && npm run build

compose-config:
	docker compose config >/dev/null && echo "compose config valid"

clean:
	rm -rf web/dist backend/.pytest_cache backend/.ruff_cache backend/.mypy_cache
