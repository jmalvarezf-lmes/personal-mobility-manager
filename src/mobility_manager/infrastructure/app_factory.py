"""
Infrastructure: AppFactory.

Builds the full application dependency graph from environment configuration
and infrastructure adapters. This keeps the FastAPI lifespan in the
presentation layer focused on lifecycle (start/stop) rather than wiring.

The factory returns an AppState dataclass containing every use case,
repository, scheduler, and channel that routers need via app.state.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.trace import TracerProvider
from sqlalchemy.engine import Engine

from mobility_manager.application.event_handlers.notification_dispatch_handler import (
    NotificationDispatchHandler,
)
from mobility_manager.application.event_handlers.ser_ticket_creation_trigger_handler import (
    SerTicketCreationTriggerHandler,
)
from mobility_manager.application.event_handlers.ser_ticket_notification_trigger_handler import (
    SerTicketNotificationTriggerHandler,
)
from mobility_manager.application.event_handlers.ser_ticket_requirement_state_handler import (
    SerTicketRequirementStateHandler,
)
from mobility_manager.application.use_cases.authenticate_google_user import (
    AuthenticateGoogleUser,
)
from mobility_manager.application.use_cases.cleanup_expired_sessions import (
    CleanupExpiredSessions,
)
from mobility_manager.application.use_cases.clear_vehicle_ser_parking_exemption import (
    ClearVehicleSerParkingExemption,
)
from mobility_manager.application.use_cases.connect_ser_ticket_provider import (
    ConnectSerTicketProvider,
)
from mobility_manager.application.use_cases.create_ser_ticket import CreateSerTicket
from mobility_manager.application.use_cases.create_session import CreateSession
from mobility_manager.application.use_cases.delete_vehicle import DeleteVehicle
from mobility_manager.application.use_cases.determine_ser_ticket_requirement import (
    DetermineSerTicketRequirement,
)
from mobility_manager.application.use_cases.disconnect_ser_ticket_provider import (
    DisconnectSerTicketProvider,
)
from mobility_manager.application.use_cases.evaluate_ser_ticket_requirement_state import (
    EvaluateSerTicketRequirementState,
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
from mobility_manager.application.use_cases.list_ser_tickets import ListSerTickets
from mobility_manager.application.use_cases.list_user_vehicles import ListUserVehicles
from mobility_manager.application.use_cases.list_vehicle_location_history import (
    ListVehicleLocationHistory,
)
from mobility_manager.application.use_cases.list_vehicle_shares import ListVehicleShares
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
from mobility_manager.application.use_cases.revoke_session import RevokeSession
from mobility_manager.application.use_cases.revoke_vehicle_share import (
    RevokeVehicleShare,
)
from mobility_manager.application.use_cases.send_notification import SendNotification
from mobility_manager.application.use_cases.ser_zone_recheck_gate import (
    SerZoneRecheckGate,
)
from mobility_manager.application.use_cases.set_vehicle_ser_parking_exemption import (
    SetVehicleSerParkingExemption,
)
from mobility_manager.application.use_cases.share_vehicle import ShareVehicle
from mobility_manager.application.use_cases.update_vehicle import UpdateVehicle
from mobility_manager.application.use_cases.validate_session import ValidateSession
from mobility_manager.config import (
    get_ambient_label_poll_interval_minutes,
    get_ambient_label_request_delay_seconds,
    get_ambient_label_retry_cooldown_hours,
    get_enabled_brands,
    get_enabled_ser_providers,
    get_encryption_key,
    get_event_publisher_max_workers,
    get_holiday_calendar_url,
    get_holiday_refresh_interval_hours,
    get_ingestion_interval_hours,
    get_ser_ticket_creation_zone_change_floor_meters,
    get_session_cleanup_interval_hours,
    get_session_cleanup_retention_days,
    get_vehicle_poll_interval_minutes,
)
from mobility_manager.domain.events.ser_ticket_created import SerTicketCreated
from mobility_manager.domain.events.ser_ticket_creation_failed import (
    SerTicketCreationFailed,
)
from mobility_manager.domain.events.ser_ticket_requirement_activated import (
    SerTicketRequirementActivated,
)
from mobility_manager.domain.events.vehicle_location_updated import (
    VehicleLocationUpdated,
)
from mobility_manager.domain.ports.notification_channel import NotificationChannelPort
from mobility_manager.domain.value_objects.brand import Brand
from mobility_manager.infrastructure.ambient_label_scheduler import (
    AmbientLabelScheduler,
)
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
from mobility_manager.infrastructure.observability.metrics_collector_adapter import (
    OpenTelemetryMetricsCollector,
)
from mobility_manager.infrastructure.parking_services.provider_registry import (
    build_providers,
    list_city_codes,
)
from mobility_manager.infrastructure.parking_services.ser_exemption_zone_rules import (
    CitySerExemptionZoneRule,
)
from mobility_manager.infrastructure.parking_services.ser_label_exemption_rules import (
    CitySerLabelExemptionRule,
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
from mobility_manager.infrastructure.repositories.postgres.session_repo import (
    PostgresSessionRepository,
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
from mobility_manager.infrastructure.repositories.postgres.user_ser_requirement_notification_repo import (
    PostgresUserSerRequirementNotificationRepository,
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
from mobility_manager.infrastructure.repositories.postgres.vehicle_ser_requirement_state_repo import (
    PostgresVehicleSerRequirementStateRepository,
)
from mobility_manager.infrastructure.repositories.postgres.vehicle_share_repo import (
    PostgresVehicleShareRepository,
)
from mobility_manager.infrastructure.scheduler import (
    ParkingIngestionScheduler,
    SessionCleanupScheduler,
)
from mobility_manager.infrastructure.ser_ticket_providers.elparking.zone_mapping_repository import (
    PostgresElParkingZoneMappingRepository,
)
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


@dataclass
class AppState:
    """Everything routers read from app.state."""

    # Repositories
    city_repo: PostgresCityRepository
    ser_zone_repo: PostgresSerZoneRepository
    user_repo: PostgresUserRepository
    user_preferences_repo: PostgresUserPreferencesRepository
    notification_preferences_repo: PostgresNotificationPreferencesRepository
    session_repo: PostgresSessionRepository
    user_notification_channel_config_repo: PostgresUserNotificationChannelConfigRepository
    vehicle_repo: PostgresVehicleRepository
    vehicle_config_repo: PostgresVehicleConfigRepository
    vehicle_location_repo: PostgresVehicleLocationRepository
    vehicle_share_repo: PostgresVehicleShareRepository
    vehicle_ser_parking_exemption_repo: PostgresVehicleSerParkingExemptionRepository
    vehicle_ambient_label_repo: PostgresVehicleAmbientLabelRepository
    ambient_label_icon_repo: PostgresAmbientLabelIconRepository
    parking_ticket_repo: PostgresParkingTicketRepository
    holiday_repo: PostgresHolidayRepository
    user_ser_provider_config_repo: PostgresUserSerProviderConfigRepository
    user_ser_requirement_notification_repo: PostgresUserSerRequirementNotificationRepository
    elparking_zone_mapping_repo: PostgresElParkingZoneMappingRepository
    ser_ticket_provider_registry: SerTicketProviderRegistry

    # Use cases / handlers exposed to routers
    find_nearest_ser_zone: FindNearestSerZone
    find_containing_ser_zone: FindContainingSerZone
    authenticate_google_user: AuthenticateGoogleUser
    create_session: CreateSession
    revoke_session: RevokeSession
    validate_session: ValidateSession
    send_notification: SendNotification
    generate_telegram_link_code: GenerateTelegramLinkCode
    list_notification_channels: ListNotificationChannels
    remove_notification_channel: RemoveNotificationChannel
    get_vehicle_ser_parking_exemption: GetVehicleSerParkingExemption
    set_vehicle_ser_parking_exemption: SetVehicleSerParkingExemption
    clear_vehicle_ser_parking_exemption: ClearVehicleSerParkingExemption
    event_publisher: InMemoryEventPublisher
    register_vehicle: RegisterVehicle
    record_vehicle_location: RecordVehicleLocation
    get_latest_vehicle_location: GetLatestVehicleLocation
    list_vehicle_location_history: ListVehicleLocationHistory
    list_ser_tickets: ListSerTickets
    list_user_vehicles: ListUserVehicles
    delete_vehicle: DeleteVehicle
    update_vehicle: UpdateVehicle
    share_vehicle: ShareVehicle
    revoke_vehicle_share: RevokeVehicleShare
    list_vehicle_shares: ListVehicleShares
    connect_ser_ticket_provider: ConnectSerTicketProvider
    create_ser_ticket: CreateSerTicket
    disconnect_ser_ticket_provider: DisconnectSerTicketProvider
    list_ser_ticket_provider_connections: ListSerTicketProviderConnections

    # Channels and providers
    notification_channels: dict[str, NotificationChannelPort]
    ser_ticket_providers: dict[str, Any]

    # Schedulers (lifespan starts/stops these)
    scheduler: ParkingIngestionScheduler
    holiday_refresh_scheduler: HolidayRefreshScheduler
    session_cleanup_scheduler: SessionCleanupScheduler
    vehicle_location_scheduler: VehicleLocationScheduler
    ambient_label_scheduler: AmbientLabelScheduler

    # Observability (lifespan shuts these down)
    tracer_provider: TracerProvider | None
    meter_provider: MeterProvider | None


def build_app_state(
    engine: Engine,
    tracer_provider: TracerProvider | None = None,
    meter_provider: MeterProvider | None = None,
) -> AppState:
    """Construct the full application dependency graph from configuration."""
    metrics_collector = OpenTelemetryMetricsCollector()

    # --- Cities and parking ---
    city_repo = PostgresCityRepository(engine)
    ser_zone_repo = PostgresSerZoneRepository(engine)
    providers = build_providers(engine=engine)
    city_use_cases = [
        (provider.city_code, IngestSerZones(provider=provider, repo=ser_zone_repo))
        for provider in providers
    ]
    find_nearest_ser_zone = FindNearestSerZone(repo=ser_zone_repo)
    find_containing_ser_zone = FindContainingSerZone(repo=ser_zone_repo)

    parking_scheduler = ParkingIngestionScheduler(
        city_use_cases=city_use_cases,
        interval_hours=get_ingestion_interval_hours(),
    )

    # --- Public holidays ---
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

    # --- Auth / users ---
    user_repo = PostgresUserRepository(engine)
    user_preferences_repo = PostgresUserPreferencesRepository(engine)
    notification_preferences_repo = PostgresNotificationPreferencesRepository(engine)
    authenticate_google_user = AuthenticateGoogleUser(
        user_repo=user_repo,
        user_preferences_repo=user_preferences_repo,
        notification_preferences_repo=notification_preferences_repo,
    )

    # --- Sessions ---
    session_repo = PostgresSessionRepository(engine)
    create_session = CreateSession(session_repo=session_repo)
    revoke_session = RevokeSession(session_repo=session_repo)
    validate_session = ValidateSession(session_repo=session_repo)
    cleanup_expired_sessions = CleanupExpiredSessions(
        session_repo=session_repo,
        retention_days=get_session_cleanup_retention_days(),
    )
    session_cleanup_scheduler = SessionCleanupScheduler(
        cleanup_use_case=cleanup_expired_sessions,
        interval_hours=get_session_cleanup_interval_hours(),
    )

    # --- Notification channels ---
    telegram_notification_channel = TelegramNotificationChannel()
    notification_channels: dict[str, NotificationChannelPort] = {
        "telegram": telegram_notification_channel
    }
    user_notification_channel_config_repo = PostgresUserNotificationChannelConfigRepository(engine)
    send_notification = SendNotification(
        channels=notification_channels,
        config_repo=user_notification_channel_config_repo,
        preferences_repo=user_preferences_repo,
    )
    generate_telegram_link_code = GenerateTelegramLinkCode()
    list_notification_channels = ListNotificationChannels(
        config_repo=user_notification_channel_config_repo
    )
    remove_notification_channel = RemoveNotificationChannel(
        config_repo=user_notification_channel_config_repo,
        preferences_repo=user_preferences_repo,
    )

    # --- Vehicles ---
    enabled_brands = get_enabled_brands()
    encryption_key: bytes | None = None
    if Brand.TOYOTA in enabled_brands:
        encryption_key = get_encryption_key()

    vehicle_repo = PostgresVehicleRepository(engine)
    vehicle_config_repo = PostgresVehicleConfigRepository(engine, encryption_key)
    vehicle_location_repo = PostgresVehicleLocationRepository(engine)
    vehicle_share_repo = PostgresVehicleShareRepository(engine)

    # --- SER parking exemption ---
    vehicle_ser_parking_exemption_repo = PostgresVehicleSerParkingExemptionRepository(engine)
    get_vehicle_ser_parking_exemption = GetVehicleSerParkingExemption(
        exemption_repo=vehicle_ser_parking_exemption_repo
    )
    set_vehicle_ser_parking_exemption = SetVehicleSerParkingExemption(
        exemption_repo=vehicle_ser_parking_exemption_repo
    )
    clear_vehicle_ser_parking_exemption = ClearVehicleSerParkingExemption(
        exemption_repo=vehicle_ser_parking_exemption_repo
    )

    # --- Ambient label ---
    vehicle_ambient_label_repo = PostgresVehicleAmbientLabelRepository(engine)
    ambient_label_icon_repo = PostgresAmbientLabelIconRepository(engine)
    dgt_ambient_label_url = os.environ.get("DGT_AMBIENT_LABEL_URL", DEFAULT_DGT_AMBIENT_LABEL_URL)
    dgt_ambient_label_provider = DgtAmbientLabelProvider(url=dgt_ambient_label_url)
    lookup_vehicle_ambient_label = LookupVehicleAmbientLabel(
        lookup_port=dgt_ambient_label_provider,
        label_repo=vehicle_ambient_label_repo,
        icon_repo=ambient_label_icon_repo,
        metrics_collector=metrics_collector,
    )

    # --- Events / SER ticket requirement ---
    event_publisher = InMemoryEventPublisher(max_workers=get_event_publisher_max_workers())
    ser_enforcement_schedule = PostgresSerEnforcementSchedule(engine)
    ser_exemption_zone_rule = CitySerExemptionZoneRule()
    ser_label_exemption_rule = CitySerLabelExemptionRule()
    parking_ticket_repo = PostgresParkingTicketRepository(engine)
    determine_ser_ticket_requirement = DetermineSerTicketRequirement(
        enforcement_schedule=ser_enforcement_schedule,
        exemption_repo=vehicle_ser_parking_exemption_repo,
        exemption_zone_rule=ser_exemption_zone_rule,
        ticket_repo=parking_ticket_repo,
        ambient_label_repo=vehicle_ambient_label_repo,
        label_exemption_rule=ser_label_exemption_rule,
    )
    ser_zone_recheck_gate = SerZoneRecheckGate(
        vehicle_location_repo=vehicle_location_repo,
        find_containing_ser_zone=find_containing_ser_zone,
        ticket_repo=parking_ticket_repo,
    )
    vehicle_ser_requirement_state_repo = PostgresVehicleSerRequirementStateRepository(engine)
    user_ser_requirement_notification_repo = PostgresUserSerRequirementNotificationRepository(engine)
    evaluate_ser_ticket_requirement_state = EvaluateSerTicketRequirementState(
        ser_zone_recheck_gate=ser_zone_recheck_gate,
        find_containing_ser_zone=find_containing_ser_zone,
        determine_ser_ticket_requirement=determine_ser_ticket_requirement,
        ticket_repo=parking_ticket_repo,
        event_publisher=event_publisher,
        movement_floor_meters=get_ser_ticket_creation_zone_change_floor_meters(),
    )
    ser_ticket_requirement_state_handler = SerTicketRequirementStateHandler(
        state_repo=vehicle_ser_requirement_state_repo,
        evaluate_state=evaluate_ser_ticket_requirement_state,
    )
    ser_ticket_notification_trigger_handler = SerTicketNotificationTriggerHandler(
        vehicle_repo=vehicle_repo,
        user_preferences_repo=user_preferences_repo,
        notification_preferences_repo=notification_preferences_repo,
        vehicle_share_repo=vehicle_share_repo,
        send_notification=send_notification,
        notification_audit_repo=user_ser_requirement_notification_repo,
    )
    event_publisher.subscribe(VehicleLocationUpdated, ser_ticket_requirement_state_handler.handle)
    event_publisher.subscribe(
        SerTicketRequirementActivated, ser_ticket_notification_trigger_handler.on_requirement_activated
    )
    event_publisher.subscribe(SerTicketCreated, ser_ticket_notification_trigger_handler.on_ticket_created)
    event_publisher.subscribe(
        SerTicketCreationFailed, ser_ticket_notification_trigger_handler.on_ticket_creation_failed
    )
    notification_dispatch_handler = NotificationDispatchHandler(
        vehicle_repo=vehicle_repo,
        vehicle_location_repo=vehicle_location_repo,
        user_preferences_repo=user_preferences_repo,
        notification_preferences_repo=notification_preferences_repo,
        vehicle_share_repo=vehicle_share_repo,
        send_notification=send_notification,
        metrics_collector=metrics_collector,
    )
    event_publisher.subscribe(VehicleLocationUpdated, notification_dispatch_handler.handle)

    # --- Vehicle use cases ---
    register_vehicle = RegisterVehicle(
        vehicle_repo=vehicle_repo,
        config_repo=vehicle_config_repo,
        enabled_brands=enabled_brands,
        lookup_ambient_label=lookup_vehicle_ambient_label,
    )
    record_vehicle_location = RecordVehicleLocation(
        location_repo=vehicle_location_repo, event_publisher=event_publisher
    )
    get_latest_vehicle_location = GetLatestVehicleLocation(location_repo=vehicle_location_repo)
    list_vehicle_location_history = ListVehicleLocationHistory(location_repo=vehicle_location_repo)
    list_ser_tickets = ListSerTickets(ticket_repo=parking_ticket_repo)
    list_user_vehicles = ListUserVehicles(
        vehicle_repo=vehicle_repo,
        location_repo=vehicle_location_repo,
        ticket_repo=parking_ticket_repo,
        share_repo=vehicle_share_repo,
    )
    delete_vehicle = DeleteVehicle(vehicle_repo=vehicle_repo)
    update_vehicle = UpdateVehicle(vehicle_repo=vehicle_repo, config_repo=vehicle_config_repo)
    share_vehicle = ShareVehicle(
        vehicle_repo=vehicle_repo,
        user_repo=user_repo,
        share_repo=vehicle_share_repo,
    )
    revoke_vehicle_share = RevokeVehicleShare(
        vehicle_repo=vehicle_repo,
        share_repo=vehicle_share_repo,
    )
    list_vehicle_shares = ListVehicleShares(
        vehicle_repo=vehicle_repo,
        share_repo=vehicle_share_repo,
        user_repo=user_repo,
    )

    # --- Schedulers ---
    brand_registry = BrandRegistry()
    pull_providers = brand_registry.build_pull_providers()
    toyota_provider = pull_providers[0] if pull_providers else None

    vehicle_location_scheduler = VehicleLocationScheduler(
        vehicle_repo=vehicle_repo,
        config_repo=vehicle_config_repo,
        location_provider=toyota_provider,
        record_use_case=record_vehicle_location,
        interval_minutes=get_vehicle_poll_interval_minutes(),
    )
    ambient_label_scheduler = AmbientLabelScheduler(
        vehicle_repo=vehicle_repo,
        label_repo=vehicle_ambient_label_repo,
        lookup_use_case=lookup_vehicle_ambient_label,
        interval_minutes=get_ambient_label_poll_interval_minutes(),
        retry_cooldown_hours=get_ambient_label_retry_cooldown_hours(),
        request_delay_seconds=get_ambient_label_request_delay_seconds(),
    )

    # --- SER ticket providers ---
    enabled_ser_providers = get_enabled_ser_providers()
    ser_encryption_key = encryption_key
    if ser_encryption_key is None and "elparking" in enabled_ser_providers:
        ser_encryption_key = get_encryption_key()

    ser_ticket_provider_registry = SerTicketProviderRegistry()
    elparking_zone_mapping_repo = PostgresElParkingZoneMappingRepository(engine)
    ser_ticket_providers = ser_ticket_provider_registry.build_providers(
        ser_zone_repo=ser_zone_repo,
        city_repo=city_repo,
        zone_mapping_repo=elparking_zone_mapping_repo,
    )
    user_ser_provider_config_repo = PostgresUserSerProviderConfigRepository(
        engine, ser_encryption_key
    )
    connect_ser_ticket_provider = ConnectSerTicketProvider(
        providers=ser_ticket_providers,
        config_repo=user_ser_provider_config_repo,
    )
    create_ser_ticket = CreateSerTicket(
        vehicle_repo=vehicle_repo,
        config_repo=user_ser_provider_config_repo,
        ticket_repo=parking_ticket_repo,
        providers=ser_ticket_providers,
        event_publisher=event_publisher,
        get_latest_vehicle_location=get_latest_vehicle_location,
    )
    disconnect_ser_ticket_provider = DisconnectSerTicketProvider(
        providers=ser_ticket_providers,
        config_repo=user_ser_provider_config_repo,
    )
    list_ser_ticket_provider_connections = ListSerTicketProviderConnections(
        config_repo=user_ser_provider_config_repo,
    )

    # --- SER ticket auto-creation ---
    ser_ticket_creation_trigger_handler = SerTicketCreationTriggerHandler(
        vehicle_repo=vehicle_repo,
        user_preferences_repo=user_preferences_repo,
        user_ser_provider_config_repo=user_ser_provider_config_repo,
        determine_ser_ticket_requirement=determine_ser_ticket_requirement,
        ser_zone_recheck_gate=ser_zone_recheck_gate,
        create_ser_ticket=create_ser_ticket,
        event_publisher=event_publisher,
        metrics_collector=metrics_collector,
    )
    event_publisher.subscribe(VehicleLocationUpdated, ser_ticket_creation_trigger_handler.handle)

    return AppState(
        city_repo=city_repo,
        ser_zone_repo=ser_zone_repo,
        user_repo=user_repo,
        user_preferences_repo=user_preferences_repo,
        notification_preferences_repo=notification_preferences_repo,
        session_repo=session_repo,
        user_notification_channel_config_repo=user_notification_channel_config_repo,
        vehicle_repo=vehicle_repo,
        vehicle_config_repo=vehicle_config_repo,
        vehicle_location_repo=vehicle_location_repo,
        vehicle_share_repo=vehicle_share_repo,
        vehicle_ser_parking_exemption_repo=vehicle_ser_parking_exemption_repo,
        vehicle_ambient_label_repo=vehicle_ambient_label_repo,
        ambient_label_icon_repo=ambient_label_icon_repo,
        parking_ticket_repo=parking_ticket_repo,
        holiday_repo=holiday_repo,
        user_ser_provider_config_repo=user_ser_provider_config_repo,
        user_ser_requirement_notification_repo=user_ser_requirement_notification_repo,
        elparking_zone_mapping_repo=elparking_zone_mapping_repo,
        ser_ticket_provider_registry=ser_ticket_provider_registry,
        find_nearest_ser_zone=find_nearest_ser_zone,
        find_containing_ser_zone=find_containing_ser_zone,
        authenticate_google_user=authenticate_google_user,
        create_session=create_session,
        revoke_session=revoke_session,
        validate_session=validate_session,
        send_notification=send_notification,
        generate_telegram_link_code=generate_telegram_link_code,
        list_notification_channels=list_notification_channels,
        remove_notification_channel=remove_notification_channel,
        get_vehicle_ser_parking_exemption=get_vehicle_ser_parking_exemption,
        set_vehicle_ser_parking_exemption=set_vehicle_ser_parking_exemption,
        clear_vehicle_ser_parking_exemption=clear_vehicle_ser_parking_exemption,
        event_publisher=event_publisher,
        register_vehicle=register_vehicle,
        record_vehicle_location=record_vehicle_location,
        get_latest_vehicle_location=get_latest_vehicle_location,
        list_vehicle_location_history=list_vehicle_location_history,
        list_ser_tickets=list_ser_tickets,
        list_user_vehicles=list_user_vehicles,
        delete_vehicle=delete_vehicle,
        update_vehicle=update_vehicle,
        share_vehicle=share_vehicle,
        revoke_vehicle_share=revoke_vehicle_share,
        list_vehicle_shares=list_vehicle_shares,
        connect_ser_ticket_provider=connect_ser_ticket_provider,
        create_ser_ticket=create_ser_ticket,
        disconnect_ser_ticket_provider=disconnect_ser_ticket_provider,
        list_ser_ticket_provider_connections=list_ser_ticket_provider_connections,
        notification_channels=notification_channels,
        ser_ticket_providers=ser_ticket_providers,
        scheduler=parking_scheduler,
        holiday_refresh_scheduler=holiday_refresh_scheduler,
        session_cleanup_scheduler=session_cleanup_scheduler,
        vehicle_location_scheduler=vehicle_location_scheduler,
        ambient_label_scheduler=ambient_label_scheduler,
        tracer_provider=tracer_provider,
        meter_provider=meter_provider,
    )
