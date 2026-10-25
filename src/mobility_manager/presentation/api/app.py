"""
Presentation: FastAPI application entry point.

Wires together all infrastructure and starts/stops the schedulers
via the FastAPI lifespan context manager. Dependency construction lives in
infrastructure.app_factory so this file focuses on HTTP presentation concerns.
"""

import logging
from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from mobility_manager.config import get_cors_origins, get_log_level, get_otel_endpoint
from mobility_manager.infrastructure.app_factory import AppState, build_app_state
from mobility_manager.infrastructure.db import get_engine
from mobility_manager.infrastructure.observability.setup import (
    init_observability,
    shutdown_observability,
)
from mobility_manager.presentation.api.limiter import limiter
from mobility_manager.presentation.api.routers.ambient_labels import (
    router as ambient_labels_router,
)
from mobility_manager.presentation.api.routers.auth import router as auth_router
from mobility_manager.presentation.api.routers.cities import router as cities_router
from mobility_manager.presentation.api.routers.config import router as config_router
from mobility_manager.presentation.api.routers.notification_preferences import (
    router as notification_preferences_router,
)
from mobility_manager.presentation.api.routers.notifications import (
    router as notifications_router,
)
from mobility_manager.presentation.api.routers.parking import router as parking_router
from mobility_manager.presentation.api.routers.preferences import (
    router as preferences_router,
)
from mobility_manager.presentation.api.routers.ser_ticket_providers import (
    router as ser_ticket_providers_router,
)
from mobility_manager.presentation.api.routers.vehicles import router as vehicles_router
from mobility_manager.presentation.api.routers.zones import router as zones_router

logging.basicConfig(
    level=get_log_level(),
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
)


def _apply_state(app: FastAPI, state: AppState) -> None:
    """Expose every AppState field on app.state for router dependencies."""
    for key, value in vars(state).items():
        setattr(app.state, key, value)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    """Set up and tear down application-level resources."""
    engine = get_engine()

    # Observability is activated only when OTEL_EXPORTER_OTLP_ENDPOINT is set.
    # When unset, the returned providers are None and every manual OTel call
    # elsewhere is an inert no-op.
    tracer_provider = None
    meter_provider = None
    if get_otel_endpoint():
        tracer_provider, meter_provider = init_observability(app, engine)

    state = build_app_state(engine, tracer_provider, meter_provider)
    _apply_state(app, state)

    # Start background schedulers.
    state.scheduler.start()
    state.holiday_refresh_scheduler.start()
    state.session_cleanup_scheduler.start()
    state.vehicle_location_scheduler.start()
    state.ambient_label_scheduler.start()

    yield

    state.scheduler.stop()
    state.holiday_refresh_scheduler.stop()
    state.vehicle_location_scheduler.stop()
    state.ambient_label_scheduler.stop()
    state.session_cleanup_scheduler.stop()
    state.event_publisher.shutdown()
    shutdown_observability(tracer_provider, meter_provider)


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
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)
app.include_router(auth_router)
app.include_router(parking_router)
app.include_router(zones_router)
app.include_router(config_router)
app.include_router(cities_router)
app.include_router(vehicles_router)
app.include_router(preferences_router)
app.include_router(ser_ticket_providers_router)
app.include_router(notifications_router)
app.include_router(notification_preferences_router)
app.include_router(ambient_labels_router)


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
