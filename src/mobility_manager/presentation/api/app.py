"""
Presentation: FastAPI application entry point.

Wires together all infrastructure and starts/stops the scheduler
via the FastAPI lifespan context manager.
"""
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI

from mobility_manager.application.use_cases.find_nearest_ser_zone import (
    FindNearestSerZone,
)
from mobility_manager.application.use_cases.ingest_ser_zones import IngestSerZones
from mobility_manager.config import (
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
app.include_router(parking_router)


@app.get("/health", tags=["health"])
def health() -> dict:
    """Health check endpoint."""
    return {"status": "ok"}
