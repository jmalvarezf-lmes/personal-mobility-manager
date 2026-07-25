.PHONY: install install-dev run test coverage lint docker-build docker-run db-migrate db-revision api

VENV    := venv
PYTHON  := $(VENV)/bin/python
PIP     := $(VENV)/bin/pip
POSTGRES_DSN :=postgresql://mobility:mobility@localhost:5432/mobility_manager

install:
	$(PIP) install -e .

install-dev:
	$(PIP) install -e ".[dev]"

run:
	$(VENV)/bin/mobility-manager

test:
	$(PYTHON) -m pytest tests/ --cov=mobility_manager --cov-report=term-missing

# Alias for `test` — AGENTS.md's documented coverage-check command; `test`
# already runs with --cov, kept as one command so the two never drift apart.
coverage: test

lint:
	$(VENV)/bin/ruff check src/ tests/
	$(VENV)/bin/mypy src/

docker-build:
	docker build -t mobility-manager .

docker-run:
	docker run --env-file .env mobility-manager

db-migrate:
	$(VENV)/bin/alembic upgrade head

# Usage: make db-revision msg="describe_your_change"
db-revision:
	$(VENV)/bin/alembic revision --autogenerate -m "$(msg)"

api:
	$(VENV)/bin/uvicorn mobility_manager.presentation.api.app:app --reload --host 0.0.0.0 --port 8000
