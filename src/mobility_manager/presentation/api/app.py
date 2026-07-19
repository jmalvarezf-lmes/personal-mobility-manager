"""
Presentation: FastAPI application entry point.

Wires together all infrastructure and starts/stops the schedulers
via the FastAPI lifespan context manager.
"""

import logging
import os
from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.trace import TracerProvider
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from mobility_manager.application.event_handlers.notification_dispatch_handler import (
    NotificationDispatchHandler,
)
from mobility_manager.application.event_handlers.ser_ticket_trigger_handler import (
    SerTicketTriggerHandler,
)
from mobility_manager.application.use_cases.authenticate_google_user import (
    AuthenticateGoogleUser,
)
from mobility_manager.application.use_cases.clear_vehicle_ser_parking_exemption import (
    ClearVehicleSerParkingExemption,
)
from mobility_manager.application.use_cases.connect_ser_ticket_provider import (
    ConnectSerTicketProvider,
)
from mobility_manager.application.use_cases.create_ser_ticket import CreateSerTicket
from mobility_manager.application.use_cases.delete_vehicle import DeleteVehicle
from mobility_manager.application.use_cases.determine_ser_ticket_requirement import (
    DetermineSerTicketRequirement,
)
from mobility_manager.application.use_cases.disconnect_ser_ticket_provider import (
    DisconnectSerTicketProvider,
)
from mobility_manager.application.use_cases.find_containing_ser_zone import (
    FindContainingSerZone,
)
from mobility_manager.application.use_cases.find_nearest_ser_zone import (
    FindNearestSerZone,
)
from mobility_manager.application.use_cases.generate_telegram_link_code import (
    GenerateTelegramLinkCode,
)
from mobility_manager.application.use_cases.get_latest_vehicle_location import (
    GetLatestVehicleLocation,
)
from mobility_manager.application.use_cases.get_vehicle_ser_parking_exemption import (
    GetVehicleSerParkingExemption,
)
from mobility_manager.application.use_cases.ingest_ser_zones import IngestSerZones
from mobility_manager.application.use_cases.list_notification_channels import (
    ListNotificationChannels,
)
from mobility_manager.application.use_cases.list_ser_ticket_provider_connections import (
    ListSerTicketProviderConnections,
)
from mobility_manager.application.use_cases.list_user_vehicles import ListUserVehicles
from mobility_manager.application.use_cases.lookup_vehicle_ambient_label import (
    LookupVehicleAmbientLabel,
)
from mobility_manager.application.use_cases.record_vehicle_location import (
    RecordVehicleLocation,
)
from mobility_manager.application.use_cases.refresh_public_holidays import (
    RefreshPublicHolidays,
)
from mobility_manager.application.use_cases.register_vehicle import RegisterVehicle
from mobility_manager.application.use_cases.remove_notification_channel import (
    RemoveNotificationChannel,
)
from mobility_manager.application.use_cases.send_notification import SendNotification
from mobility_manager.application.use_cases.set_vehicle_ser_parking_exemption import (
    SetVehicleSerParkingExemption,
)
from mobility_manager.application.use_cases.update_vehicle import UpdateVehicle
from mobility_manager.config import (
    get_ambient_label_poll_interval_minutes,
    get_ambient_label_request_delay_seconds,
    get_ambient_label_retry_cooldown_hours,
    get_cors_origins,
    get_enabled_brands,
    get_enabled_ser_providers,
    get_encryption_key,
    get_holiday_calendar_url,
    get_holiday_refresh_interval_hours,
    get_ingestion_interval_hours,
    get_log_level,
    get_otel_endpoint,
    get_vehicle_poll_interval_minutes,
)
from mobility_manager.domain.events.vehicle_location_updated import (
    VehicleLocationUpdated,
)
from mobility_manager.domain.ports.notification_channel import NotificationChannelPort
from mobility_manager.domain.value_objects.brand import Brand
from mobility_manager.infrastructure.ambient_label_scheduler import (
    AmbientLabelScheduler,
)
from mobility_manager.infrastructure.db import get_engine
from mobility_manager.infrastructure.events.in_memory_event_publisher import (
    InMemoryEventPublisher,
)
from mobility_manager.infrastructure.holiday_calendar.google_calendar_provider import (
    GoogleCalendarHolidayProvider,
)
from mobility_manager.infrastructure.holiday_refresh_scheduler import (
    HolidayRefreshScheduler,
)
from mobility_manager.infrastructure.notification_channels.telegram.channel import (
    TelegramNotificationChannel,
)
from mobility_manager.infrastructure.observability.setup import (
    init_observability,
    shutdown_observability,
)
from mobility_manager.infrastructure.parking_services.provider_registry import (
    build_providers,
    list_city_codes,
)
from mobility_manager.infrastructure.repositories.postgres.ambient_label_icon_repo import (
    PostgresAmbientLabelIconRepository,
)
from mobility_manager.infrastructure.repositories.postgres.city_repo import (
    PostgresCityRepository,
)
from mobility_manager.infrastructure.repositories.postgres.holiday_repo import (
    PostgresHolidayRepository,
)
from mobility_manager.infrastructure.repositories.postgres.notification_preferences_repo import (
    PostgresNotificationPreferencesRepository,
)
from mobility_manager.infrastructure.repositories.postgres.parking_ticket_repo import (
    PostgresParkingTicketRepository,
)
from mobility_manager.infrastructure.repositories.postgres.ser_enforcement_schedule_repo import (
    PostgresSerEnforcementSchedule,
)
from mobility_manager.infrastructure.repositories.postgres.ser_zone_repo import (
    PostgresSerZoneRepository,
)
from mobility_manager.infrastructure.repositories.postgres.user_notification_channel_config_repo import (
    PostgresUserNotificationChannelConfigRepository,
)
from mobility_manager.infrastructure.repositories.postgres.user_preferences_repo import (
    PostgresUserPreferencesRepository,
)
from mobility_manager.infrastructure.repositories.postgres.user_repo import (
    PostgresUserRepository,
)
from mobility_manager.infrastructure.repositories.postgres.user_ser_provider_config_repo import (
    PostgresUserSerProviderConfigRepository,
)
from mobility_manager.infrastructure.repositories.postgres.vehicle_ambient_label_repo import (
    PostgresVehicleAmbientLabelRepository,
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
from mobility_manager.infrastructure.repositories.postgres.vehicle_ser_parking_exemption_repo import (
    PostgresVehicleSerParkingExemptionRepository,
)
from mobility_manager.infrastructure.scheduler import ParkingIngestionScheduler
from mobility_manager.infrastructure.ser_ticket_providers.registry import (
    SerTicketProviderRegistry,
)
from mobility_manager.infrastructure.vehicle_location_scheduler import (
    VehicleLocationScheduler,
)
from mobility_manager.infrastructure.vehicle_providers.brand_registry import (
    BrandRegistry,
)
from mobility_manager.infrastructure.vehicle_providers.dgt.ambient_label_provider import (
    DEFAULT_DGT_AMBIENT_LABEL_URL,
    DgtAmbientLabelProvider,
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


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    """Set up and tear down application-level resources."""
    engine = get_engine()

    # --- Observability (OpenTelemetry) ---
    # Activation is implicit: only wired up when OTEL_EXPORTER_OTLP_ENDPOINT
    # is configured (see config.get_otel_endpoint() and
    # infrastructure/observability/setup.py's module docstring). When unset,
    # tracer_provider/meter_provider stay None and every manual span/metric
    # call elsewhere in the app is an inert OTel API no-op — no behavior
    # change, no crash, no new required env var.
    tracer_provider: TracerProvider | None = None
    meter_provider: MeterProvider | None = None
    if get_otel_endpoint():
        tracer_provider, meter_provider = init_observability(app, engine)

    # --- Cities (city-registry) ---
    # Built early: GET /parking/ser-zones (below) and GET /cities both need
    # the live cities table as their sole source of truth for which city
    # codes are valid — see add-vehicle-ser-parking-exemption design.md D6/D7.
    city_repo = PostgresCityRepository(engine)
    app.state.city_repo = city_repo

    # --- Parking (existing) ---
    repo = PostgresSerZoneRepository(engine)
    providers = build_providers(engine=engine)
    city_use_cases = [(provider.city_code, IngestSerZones(provider=provider, repo=repo)) for provider in providers]
    find_uc = FindNearestSerZone(repo=repo)
    find_containing_uc = FindContainingSerZone(repo=repo)
    app.state.find_nearest_ser_zone = find_uc
    app.state.find_containing_ser_zone = find_containing_uc
    app.state.ser_zone_repo = repo

    parking_scheduler = ParkingIngestionScheduler(
        city_use_cases=city_use_cases,
        interval_hours=get_ingestion_interval_hours(),
    )
    parking_scheduler.start()
    app.state.scheduler = parking_scheduler

    # --- Public holiday calendar ---
    # Independent of which cities have an implemented parking-data provider
    # (build_providers() above may skip a `cities` row with no matching
    # implementation, logging a warning) — the holiday refresh applies to
    # every city registered in `cities`, since a city's enforcement-hours
    # check (PostgresSerEnforcementSchedule) depends on holiday data for
    # its own city_code regardless of whether a parking provider exists yet
    # (design.md D7).
    city_codes = list_city_codes(engine)

    holiday_repo = PostgresHolidayRepository(engine)
    holiday_calendar_provider = GoogleCalendarHolidayProvider(url=get_holiday_calendar_url())
    refresh_public_holidays_uc = RefreshPublicHolidays(
        provider=holiday_calendar_provider,
        holiday_repo=holiday_repo,
        city_codes=city_codes,
    )
    holiday_refresh_scheduler = HolidayRefreshScheduler(
        refresh_use_case=refresh_public_holidays_uc,
        holiday_repo=holiday_repo,
        city_codes=city_codes,
        interval_hours=get_holiday_refresh_interval_hours(),
    )
    holiday_refresh_scheduler.start()
    app.state.holiday_repo = holiday_repo
    app.state.holiday_refresh_scheduler = holiday_refresh_scheduler

    # --- Auth (Users) ---
    user_repo = PostgresUserRepository(engine)
    user_preferences_repo = PostgresUserPreferencesRepository(engine)
    notification_preferences_repo = PostgresNotificationPreferencesRepository(engine)
    authenticate_google_user_uc = AuthenticateGoogleUser(
        user_repo=user_repo,
        user_preferences_repo=user_preferences_repo,
        notification_preferences_repo=notification_preferences_repo,
    )
    app.state.user_repo = user_repo
    app.state.user_preferences_repo = user_preferences_repo
    app.state.notification_preferences_repo = notification_preferences_repo
    app.state.authenticate_google_user = authenticate_google_user_uc

    # --- Notification channels ---
    # Moved ahead of --- Vehicles --- and --- Events --- (was originally
    # built much later, right before the lifespan's final `yield`):
    # NotificationDispatchHandler (constructed in the Events block below)
    # now needs send_notification_uc at construction time, so it must exist
    # by then. user_preferences_repo (from Auth, above) is its only
    # dependency, so this block only needed to move earlier, not depend on
    # anything from Vehicles.
    telegram_notification_channel = TelegramNotificationChannel()
    notification_channels: dict[str, NotificationChannelPort] = {"telegram": telegram_notification_channel}
    user_notification_channel_config_repo = PostgresUserNotificationChannelConfigRepository(engine)
    send_notification_uc = SendNotification(
        channels=notification_channels,
        config_repo=user_notification_channel_config_repo,
        preferences_repo=user_preferences_repo,
    )
    generate_telegram_link_code_uc = GenerateTelegramLinkCode()
    list_notification_channels_uc = ListNotificationChannels(config_repo=user_notification_channel_config_repo)
    remove_notification_channel_uc = RemoveNotificationChannel(
        config_repo=user_notification_channel_config_repo,
        preferences_repo=user_preferences_repo,
    )
    app.state.notification_channels = notification_channels
    app.state.user_notification_channel_config_repo = user_notification_channel_config_repo
    app.state.send_notification = send_notification_uc
    app.state.generate_telegram_link_code = generate_telegram_link_code_uc
    app.state.list_notification_channels = list_notification_channels_uc
    app.state.remove_notification_channel = remove_notification_channel_uc

    # --- Vehicles ---
    enabled_brands = get_enabled_brands()

    # Get encryption key only when Toyota is enabled (raises RuntimeError if missing)
    encryption_key: bytes | None = None
    if Brand.TOYOTA in enabled_brands:
        encryption_key = get_encryption_key()

    vehicle_repo = PostgresVehicleRepository(engine)
    vehicle_config_repo = PostgresVehicleConfigRepository(engine, encryption_key)
    vehicle_location_repo = PostgresVehicleLocationRepository(engine)

    # --- SER parking exemption ---
    # Built here (ahead of --- Events ---) since DetermineSerTicketRequirement
    # (constructed in the Events block below) now needs it injected — see
    # add-vehicle-ser-parking-exemption design.md D4.
    vehicle_ser_parking_exemption_repo = PostgresVehicleSerParkingExemptionRepository(engine)
    get_vehicle_ser_parking_exemption_uc = GetVehicleSerParkingExemption(
        exemption_repo=vehicle_ser_parking_exemption_repo
    )
    set_vehicle_ser_parking_exemption_uc = SetVehicleSerParkingExemption(
        exemption_repo=vehicle_ser_parking_exemption_repo
    )
    clear_vehicle_ser_parking_exemption_uc = ClearVehicleSerParkingExemption(
        exemption_repo=vehicle_ser_parking_exemption_repo
    )
    app.state.vehicle_ser_parking_exemption_repo = vehicle_ser_parking_exemption_repo
    app.state.get_vehicle_ser_parking_exemption = get_vehicle_ser_parking_exemption_uc
    app.state.set_vehicle_ser_parking_exemption = set_vehicle_ser_parking_exemption_uc
    app.state.clear_vehicle_ser_parking_exemption = clear_vehicle_ser_parking_exemption_uc

    # --- Ambient label (DGT distintivo ambiental) ---
    # Additive and off the request path except for the best-effort call
    # inside RegisterVehicle.execute() below, which is itself try/except
    # wrapped so DGT's availability never affects registration (see
    # add-ambient-label-lookup design.md decision 4).
    vehicle_ambient_label_repo = PostgresVehicleAmbientLabelRepository(engine)
    ambient_label_icon_repo = PostgresAmbientLabelIconRepository(engine)
    dgt_ambient_label_url = os.environ.get("DGT_AMBIENT_LABEL_URL", DEFAULT_DGT_AMBIENT_LABEL_URL)
    dgt_ambient_label_provider = DgtAmbientLabelProvider(url=dgt_ambient_label_url)
    lookup_vehicle_ambient_label_uc = LookupVehicleAmbientLabel(
        lookup_port=dgt_ambient_label_provider,
        label_repo=vehicle_ambient_label_repo,
        icon_repo=ambient_label_icon_repo,
    )
    app.state.vehicle_ambient_label_repo = vehicle_ambient_label_repo
    app.state.ambient_label_icon_repo = ambient_label_icon_repo

    # --- Events (vehicle-location-events) ---
    # NotificationDispatchHandler now needs vehicle_repo, vehicle_location_repo
    # (both constructed just above), user_preferences_repo and
    # notification_preferences_repo (Auth block), and send_notification_uc
    # (Notification channels block, now moved ahead of Vehicles) — all
    # already exist by this point. record_uc below still needs
    # event_publisher, so event_publisher's construction stays here rather
    # than moving down with the rest of this block.
    event_publisher = InMemoryEventPublisher()
    ser_enforcement_schedule = PostgresSerEnforcementSchedule(engine)
    determine_ser_ticket_requirement_uc = DetermineSerTicketRequirement(
        enforcement_schedule=ser_enforcement_schedule,
        exemption_repo=vehicle_ser_parking_exemption_repo,
    )
    ser_ticket_trigger_handler = SerTicketTriggerHandler(
        vehicle_repo=vehicle_repo,
        vehicle_location_repo=vehicle_location_repo,
        user_preferences_repo=user_preferences_repo,
        notification_preferences_repo=notification_preferences_repo,
        find_containing_ser_zone=find_containing_uc,
        determine_ser_ticket_requirement=determine_ser_ticket_requirement_uc,
        send_notification=send_notification_uc,
    )
    event_publisher.subscribe(VehicleLocationUpdated, ser_ticket_trigger_handler.handle)
    notification_dispatch_handler = NotificationDispatchHandler(
        vehicle_repo=vehicle_repo,
        vehicle_location_repo=vehicle_location_repo,
        user_preferences_repo=user_preferences_repo,
        notification_preferences_repo=notification_preferences_repo,
        send_notification=send_notification_uc,
    )
    event_publisher.subscribe(VehicleLocationUpdated, notification_dispatch_handler.handle)
    app.state.event_publisher = event_publisher

    register_uc = RegisterVehicle(
        vehicle_repo=vehicle_repo,
        config_repo=vehicle_config_repo,
        enabled_brands=enabled_brands,
        lookup_ambient_label=lookup_vehicle_ambient_label_uc,
    )
    record_uc = RecordVehicleLocation(location_repo=vehicle_location_repo, event_publisher=event_publisher)
    get_latest_uc = GetLatestVehicleLocation(location_repo=vehicle_location_repo)

    list_uc = ListUserVehicles(vehicle_repo=vehicle_repo, location_repo=vehicle_location_repo)
    delete_uc = DeleteVehicle(vehicle_repo=vehicle_repo)
    update_uc = UpdateVehicle(vehicle_repo=vehicle_repo, config_repo=vehicle_config_repo)

    app.state.register_vehicle = register_uc
    app.state.record_vehicle_location = record_uc
    app.state.get_latest_vehicle_location = get_latest_uc
    app.state.list_user_vehicles = list_uc
    app.state.delete_vehicle = delete_uc
    app.state.update_vehicle = update_uc
    app.state.vehicle_config_repo = vehicle_config_repo
    app.state.vehicle_repo = vehicle_repo

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

    ambient_label_scheduler = AmbientLabelScheduler(
        vehicle_repo=vehicle_repo,
        label_repo=vehicle_ambient_label_repo,
        lookup_use_case=lookup_vehicle_ambient_label_uc,
        interval_minutes=get_ambient_label_poll_interval_minutes(),
        retry_cooldown_hours=get_ambient_label_retry_cooldown_hours(),
        request_delay_seconds=get_ambient_label_request_delay_seconds(),
    )
    ambient_label_scheduler.start()
    app.state.ambient_label_scheduler = ambient_label_scheduler

    # --- SER ticket provider ---
    # Reuse the Toyota encryption key if already resolved above. ElParking is
    # enabled by default (ENABLED_SER_PROVIDERS defaults to "elparking"), so
    # ENCRYPTION_KEY is now a hard startup requirement here too — no
    # try/except, mirroring the non-swallowing Toyota pattern above: a real
    # RuntimeError propagates and crashes startup rather than being silenced.
    enabled_ser_providers = get_enabled_ser_providers()
    ser_encryption_key = encryption_key
    if ser_encryption_key is None and "elparking" in enabled_ser_providers:
        ser_encryption_key = get_encryption_key()

    ser_ticket_provider_registry = SerTicketProviderRegistry()
    ser_ticket_providers = ser_ticket_provider_registry.build_providers()
    user_ser_provider_config_repo = PostgresUserSerProviderConfigRepository(engine, ser_encryption_key)
    parking_ticket_repo = PostgresParkingTicketRepository(engine)
    connect_ser_ticket_provider_uc = ConnectSerTicketProvider(
        providers=ser_ticket_providers,
        config_repo=user_ser_provider_config_repo,
    )
    create_ser_ticket_uc = CreateSerTicket(
        vehicle_repo=vehicle_repo,
        config_repo=user_ser_provider_config_repo,
        ticket_repo=parking_ticket_repo,
        providers=ser_ticket_providers,
    )
    disconnect_ser_ticket_provider_uc = DisconnectSerTicketProvider(
        providers=ser_ticket_providers,
        config_repo=user_ser_provider_config_repo,
    )
    list_ser_ticket_provider_connections_uc = ListSerTicketProviderConnections(
        config_repo=user_ser_provider_config_repo,
    )
    app.state.ser_ticket_provider_registry = ser_ticket_provider_registry
    app.state.user_ser_provider_config_repo = user_ser_provider_config_repo
    app.state.parking_ticket_repo = parking_ticket_repo
    app.state.connect_ser_ticket_provider = connect_ser_ticket_provider_uc
    app.state.create_ser_ticket = create_ser_ticket_uc
    app.state.disconnect_ser_ticket_provider = disconnect_ser_ticket_provider_uc
    app.state.list_ser_ticket_provider_connections = list_ser_ticket_provider_connections_uc

    yield

    parking_scheduler.stop()
    holiday_refresh_scheduler.stop()
    vehicle_location_scheduler.stop()
    ambient_label_scheduler.stop()
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
