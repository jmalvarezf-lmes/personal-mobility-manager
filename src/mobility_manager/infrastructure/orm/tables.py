"""
Shared SQLAlchemy table definitions.

This is the single source of truth for all table schemas. Both repository
implementations and Alembic's env.py import from here so autogenerate
can discover every table in one place.
"""

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    LargeBinary,
    MetaData,
    SmallInteger,
    String,
    Table,
    Text,
    Time,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB

metadata = MetaData()

cities_table = Table(
    "cities",
    metadata,
    Column("code", Text, primary_key=True),
    Column("name", Text, nullable=False),
)

ser_zones_table = Table(
    "ser_zones",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("city_code", Text, ForeignKey("cities.code"), nullable=False),
    Column("zone_number", String(10), nullable=False),
    Column("zone_type", String(50), nullable=False),
    Column("district", Text, nullable=False),
    Column("spot_count", Integer, nullable=False, server_default="-1"),
    Column("geometry_wkt", Text, nullable=False),  # WKT Polygon/MultiPolygon, EPSG:25830
    UniqueConstraint("city_code", "zone_number", "zone_type", name="uq_ser_zones_city_zone_number_zone_type"),
)

ser_zone_streets_table = Table(
    "ser_zone_streets",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("city_code", Text, ForeignKey("cities.code"), nullable=False),
    Column("zone_number", String(10), nullable=False),
    Column("zone_type", String(50), nullable=False),
    Column("street_name", Text, nullable=False),
    Index("idx_ser_zone_streets_zone", "city_code", "zone_number", "zone_type"),
)

ser_zone_areas_table = Table(
    "ser_zone_areas",
    metadata,
    Column("city_code", Text, ForeignKey("cities.code"), primary_key=True),
    Column("zone_number", String(10), primary_key=True),
    Column("neighbourhood", Text, nullable=False),
    Column("geometry_wkt", Text, nullable=False),  # WKT Polygon/MultiPolygon, EPSG:25830
)

ser_timetable_weekday_hours_table = Table(
    "ser_timetable_weekday_hours",
    metadata,
    Column("city_code", Text, ForeignKey("cities.code"), primary_key=True),
    Column("weekday", SmallInteger, primary_key=True),  # 0=Monday..6=Sunday
    Column("start_time", Time, nullable=False),
    Column("end_time", Time, nullable=False),
    Column("active", Boolean, nullable=False),
)

ser_timetable_exception_table = Table(
    "ser_timetable_exception",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("city_code", Text, ForeignKey("cities.code"), nullable=False),
    Column("recurrence", Text, nullable=False),  # 'month' | 'fixed_date'
    Column("month", SmallInteger, nullable=True),  # populated only for recurrence='month'
    Column("month_day", Text, nullable=True),  # 'MM-DD', populated only for recurrence='fixed_date'
    Column("start_time", Time, nullable=False),
    Column("end_time", Time, nullable=False),
    Column("description", Text, nullable=False),
)

holidays_table = Table(
    "holidays",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("city_code", Text, ForeignKey("cities.code"), nullable=False),
    Column("date", Date, nullable=False),
    Column("name", Text, nullable=False),
    Column("source", Text, nullable=False),  # 'ical_national' | 'manual'
    UniqueConstraint("city_code", "date", "source", name="uq_holidays_city_date_source"),
)

users_table = Table(
    "users",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("google_sub", Text, nullable=False, unique=True),
    Column("email", Text, nullable=False),
    Column("display_name", Text, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
)

vehicles_table = Table(
    "vehicles",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("brand", String(20), nullable=False),
    Column("display_name", String(255), nullable=False),
    Column("vin", String(50), nullable=True),
    Column("license_plate", String(20), nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("user_id", Uuid, ForeignKey("users.id"), nullable=False),
)

user_preferences_table = Table(
    "user_preferences",
    metadata,
    Column("user_id", Uuid, ForeignKey("users.id"), primary_key=True),
    Column("default_ticket_duration_minutes", Integer, nullable=False, server_default="60"),
    Column("auto_create_ticket", Boolean, nullable=False, server_default="false"),
    Column("preferred_notification_channel", Text, nullable=True),
    Column("notification_language", Text, nullable=True),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)

vehicle_configs_table = Table(
    "vehicle_configs",
    metadata,
    Column("vehicle_id", Uuid, ForeignKey("vehicles.id"), primary_key=True),
    Column("brand", String(20), nullable=False),
    Column("encrypted_payload", LargeBinary, nullable=True),  # Toyota only (Fernet)
    Column("location_token", String(64), nullable=True),  # Generic only (cleartext)
    Column("updated_at", DateTime(timezone=True), nullable=False),
)

vehicle_locations_table = Table(
    "vehicle_locations",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("vehicle_id", Uuid, ForeignKey("vehicles.id"), nullable=False),
    Column("latitude", Float, nullable=False),
    Column("longitude", Float, nullable=False),
    Column("recorded_at", DateTime(timezone=True), nullable=False),
    Column("received_at", DateTime(timezone=True), nullable=False),
    Column("source", String(10), nullable=False),
)

user_ser_provider_configs_table = Table(
    "user_ser_provider_configs",
    metadata,
    Column("user_id", Uuid, ForeignKey("users.id"), primary_key=True),
    Column("provider", Text, primary_key=True),
    Column("encrypted_payload", LargeBinary, nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)

user_notification_channel_configs_table = Table(
    "user_notification_channel_configs",
    metadata,
    Column("user_id", Uuid, ForeignKey("users.id"), primary_key=True),
    Column("channel", Text, primary_key=True),
    Column("config", Text, nullable=False),  # JSON, cleartext — not a credential, see design.md decision 3
    Column("updated_at", DateTime(timezone=True), nullable=False),
)

notification_types_table = Table(
    "notification_types",
    metadata,
    Column("key", Text, primary_key=True),
    Column("label", Text, nullable=False),
    Column("config_schema", JSONB, nullable=False),
)

user_notification_preferences_table = Table(
    "user_notification_preferences",
    metadata,
    Column("user_id", Uuid, ForeignKey("users.id"), primary_key=True),
    Column("type_key", Text, ForeignKey("notification_types.key"), primary_key=True),
    Column("enabled", Boolean, nullable=False),
    Column("config", JSONB, nullable=False, server_default="{}"),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)

parking_tickets_table = Table(
    "parking_tickets",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("vehicle_id", Uuid, ForeignKey("vehicles.id"), nullable=False),
    Column("user_id", Uuid, ForeignKey("users.id"), nullable=False),
    Column("provider", Text, nullable=False),
    Column("duration_minutes", Integer, nullable=False),
    Column("provider_reference", Text, nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
)

vehicle_ambient_labels_table = Table(
    "vehicle_ambient_labels",
    metadata,
    Column("vehicle_id", Uuid, ForeignKey("vehicles.id"), primary_key=True),
    Column("label", String(10), nullable=True),
    Column("status", String(20), nullable=False),
    Column("last_checked_at", DateTime(timezone=True), nullable=True),
)

ambient_label_icons_table = Table(
    "ambient_label_icons",
    metadata,
    Column("label", String(10), primary_key=True),
    Column("image_bytes", LargeBinary, nullable=False),
    Column("content_type", String(100), nullable=False),
    Column("fetched_at", DateTime(timezone=True), nullable=False),
)

vehicle_ser_parking_exemptions_table = Table(
    "vehicle_ser_parking_exemptions",
    metadata,
    Column("vehicle_id", Uuid, ForeignKey("vehicles.id", ondelete="CASCADE"), primary_key=True),
    Column("city_code", Text, nullable=False),
    Column("zone_number", String(10), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    ForeignKeyConstraint(
        ["city_code", "zone_number"],
        ["ser_zone_areas.city_code", "ser_zone_areas.zone_number"],
        name="fk_vehicle_ser_parking_exemptions_zone_area",
        ondelete="CASCADE",
    ),
)
