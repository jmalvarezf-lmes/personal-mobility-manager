"""
Presentation: FastAPI application entry point.

Wires together all infrastructure and starts/stops the schedulers
via the FastAPI lifespan context manager.
"""
from collections.abc import Awaitable, Callable
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
from mobility_manager.application.use_cases.get_latest_vehicle_location import (
    GetLatestVehicleLocation,
)
from mobility_manager.application.use_cases.ingest_ser_zones import IngestSerZones
from mobility_manager.application.use_cases.record_vehicle_location import (
    RecordVehicleLocation,
)
from mobility_manager.application.use_cases.register_vehicle import RegisterVehicle
from mobility_manager.config import (
    get_cors_origins,
    get_enabled_brands,
    get_encryption_key,
    get_ingestion_interval_hours,
    get_vehicle_poll_interval_minutes,
)
from mobility_manager.domain.value_objects.brand import Brand
from mobility_manager.infrastructure.db import get_engine
from mobility_manager.infrastructure.parking_services.provider_registry import (
    build_providers,
)
from mobility_manager.infrastructure.repositories.postgres.ser_zone_repo import (
    PostgresSerZoneRepository,
)
from mobility_manager.infrastructure.repositories.postgres.vehicle_config_repo import (
    PostgresVehicleConfigRepository,
)
from mobility_manager.infrastructure.repositories.postgres.vehicle_location_repo import (
    PostgresVehicleLocationRepository,
)
from mobility_manager.infrastructure.repositories.postgres.vehicle_repo import (
    PostgresVehicleRepository,
)
from mobility_manager.infrastructure.scheduler import ParkingIngestionScheduler
from mobility_manager.infrastructure.vehicle_location_scheduler import (
    VehicleLocationScheduler,
)
from mobility_manager.infrastructure.vehicle_providers.brand_registry import (
    BrandRegistry,
)
from mobility_manager.presentation.api.limiter import limiter
from mobility_manager.presentation.api.routers.config import router as config_router
from mobility_manager.presentation.api.routers.parking import router as parking_router
from mobility_manager.presentation.api.routers.vehicles import router as vehicles_router
from mobility_manager.presentation.api.routers.zones import router as zones_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Set up and tear down application-level resources."""
    engine = get_engine()

    # --- Parking (existing) ---
    repo = PostgresSerZoneRepository(engine)
    providers = build_providers()
    city_use_cases = [
        (provider.city_code, IngestSerZones(provider=provider, repo=repo))
        for provider in providers
    ]
    find_uc = FindNearestSerZone(repo=repo)
    app.state.find_nearest_ser_zone = find_uc
    app.state.ser_zone_repo = repo

    parking_scheduler = ParkingIngestionScheduler(
        city_use_cases=city_use_cases,
        interval_hours=get_ingestion_interval_hours(),
    )
    parking_scheduler.start()
    app.state.scheduler = parking_scheduler

    # --- Vehicles ---
    enabled_brands = get_enabled_brands()

    # Get encryption key only when Toyota is enabled (raises RuntimeError if missing)
    encryption_key: bytes | None = None
    if Brand.TOYOTA in enabled_brands:
        encryption_key = get_encryption_key()

    vehicle_repo = PostgresVehicleRepository(engine)
    vehicle_config_repo = PostgresVehicleConfigRepository(engine, encryption_key)
    vehicle_location_repo = PostgresVehicleLocationRepository(engine)

    register_uc = RegisterVehicle(
        vehicle_repo=vehicle_repo,
        config_repo=vehicle_config_repo,
        enabled_brands=enabled_brands,
    )
    record_uc = RecordVehicleLocation(location_repo=vehicle_location_repo)
    get_latest_uc = GetLatestVehicleLocation(location_repo=vehicle_location_repo)

    app.state.register_vehicle = register_uc
    app.state.record_vehicle_location = record_uc
    app.state.get_latest_vehicle_location = get_latest_uc
    app.state.vehicle_config_repo = vehicle_config_repo

    # Brand registry validates ENCRYPTION_KEY when Toyota is enabled
    brand_registry = BrandRegistry()
    pull_providers = brand_registry.build_pull_providers()
    toyota_provider = pull_providers[0] if pull_providers else None

    vehicle_location_scheduler = VehicleLocationScheduler(
        vehicle_repo=vehicle_repo,
        config_repo=vehicle_config_repo,
        location_provider=toyota_provider,
        record_use_case=record_uc,
        interval_minutes=get_vehicle_poll_interval_minutes(),
    )
    vehicle_location_scheduler.start()
    app.state.vehicle_location_scheduler = vehicle_location_scheduler

    yield

    parking_scheduler.stop()
    vehicle_location_scheduler.stop()


app = FastAPI(
    title="Personal Mobility Manager API",
    description="REST API for personal mobility management, including Madrid SER zone lookup.",
    version="0.1.0",
    lifespan=lifespan,
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_origins(),
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
app.include_router(parking_router)
app.include_router(zones_router)
app.include_router(config_router)
app.include_router(vehicles_router)


@app.middleware("http")
async def add_security_headers(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Content-Security-Policy"] = "default-src 'none'"
    response.headers["X-XSS-Protection"] = "0"
    return response


@app.get("/health", tags=["health"])
def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok"}
