#!/bin/sh
set -e

echo "Running database migrations..."
alembic upgrade head

echo "Starting application..."
exec uvicorn mobility_manager.presentation.api.app:app \
    --host 0.0.0.0 \
    --port 8000
