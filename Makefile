.PHONY: install install-dev run test lint docker-build docker-run db-migrate api

install:
	pip install -e .

install-dev:
	pip install -r requirements-dev.txt && pip install -e .

run:
	mobility-manager

test:
	pytest tests/ --cov=mobility_manager --cov-report=term-missing

lint:
	ruff check src/ tests/
	mypy src/

docker-build:
	docker build -t mobility-manager .

docker-run:
	docker run --env-file .env mobility-manager

db-migrate:
	psql $$POSTGRES_DSN -f db/migrations/001_create_ser_zones.sql

api:
	uvicorn mobility_manager.presentation.api.app:app --reload --host 0.0.0.0 --port 8000
