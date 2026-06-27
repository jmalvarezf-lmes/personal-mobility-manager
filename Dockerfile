FROM python:3.14-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ src/
COPY pyproject.toml .
RUN pip install --no-cache-dir -e .

COPY alembic/ alembic/
COPY alembic.ini .
COPY docker-entrypoint.sh .

ENTRYPOINT ["./docker-entrypoint.sh"]
