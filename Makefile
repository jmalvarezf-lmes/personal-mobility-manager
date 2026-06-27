.PHONY: install install-dev run test lint docker-build docker-run db-migrate db-revision api

VENV    := .venv
PYTHON  := $(VENV)/bin/python
PIP     := $(VENV)/bin/pip

install:
	$(PIP) install -e .

install-dev:
	$(PIP) install -r requirements-dev.txt && $(PIP) install -e .

run:
	$(VENV)/bin/mobility-manager

test:
	$(PYTHON) -m pytest tests/ --cov=mobility_manager --cov-report=term-missing

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
