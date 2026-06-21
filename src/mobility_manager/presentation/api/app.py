"""
Presentation: FastAPI application entry point.

Wires together all infrastructure and starts/stops the scheduler
via the FastAPI lifespan context manager.
"""
from collections.abc import Callable
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from mobility_manager.application.use_cases.find_nearest_ser_zone import (
    FindNearestSerZone,
)
from mobility_manager.application.use_cases.ingest_ser_zones import IngestSerZones
from mobility_manager.config import (
    get_cors_origins,
    get_ingestion_interval_hours,
    get_madrid_callejero_url,
)
from mobility_manager.infrastructure.db import get_engine
from mobility_manager.infrastructure.parking_services.madrid.csv_parser import (
    CallejeroCsvParser,
)
from mobility_manager.infrastructure.parking_services.madrid.data_fetcher import (
    MadridCallejeroCsvFetcher,
)
from mobility_manager.infrastructure.repositories.postgres.ser_zone_repo import (
    PostgresSerZoneRepository,
)
from mobility_manager.infrastructure.scheduler import SerZoneIngestionScheduler
from mobility_manager.presentation.api.limiter import limiter
from mobility_manager.presentation.api.routers.parking import router as parking_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Set up and tear down application-level resources."""
    engine = get_engine()
    repo = PostgresSerZoneRepository(engine)
    fetcher = MadridCallejeroCsvFetcher(url=get_madrid_callejero_url())
    parser = CallejeroCsvParser()
    ingest_uc = IngestSerZones(fetcher=fetcher, parser=parser, repo=repo)
    find_uc = FindNearestSerZone(repo=repo)

    app.state.find_nearest_ser_zone = find_uc

    scheduler = SerZoneIngestionScheduler(
        ingest_uc, interval_hours=get_ingestion_interval_hours()
    )
    scheduler.start()
    app.state.scheduler = scheduler

    yield

    scheduler.stop()


app = FastAPI(
    title="Personal Mobility Manager API",
    description="REST API for personal mobility management, including Madrid SER zone lookup.",
    version="0.1.0",
    lifespan=lifespan,
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_origins(),
    allow_methods=["GET"],
    allow_headers=["*"],
)
app.include_router(parking_router)


@app.middleware("http")
async def add_security_headers(request: Request, call_next: Callable) -> Response:
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Content-Security-Policy"] = "default-src 'none'"
    response.headers["X-XSS-Protection"] = "0"
    return response


@app.get("/health", tags=["health"])
def health() -> dict:
    """Health check endpoint."""
    return {"status": "ok"}
