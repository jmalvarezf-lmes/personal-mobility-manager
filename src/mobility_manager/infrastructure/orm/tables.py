"""
Shared SQLAlchemy table definitions.

This is the single source of truth for all table schemas. Both repository
implementations and Alembic's env.py import from here so autogenerate
can discover every table in one place.
"""

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    LargeBinary,
    MetaData,
    String,
    Table,
    Text,
    Uuid,
)

metadata = MetaData()

ser_zones_table = Table(
    "ser_zones",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("street_name", Text, nullable=False),
    Column("zone_type", String(50), nullable=False),
    Column("spot_count", Integer, nullable=False, server_default="-1"),
    Column("latitude", Float, nullable=False),  # WGS84 — bounding-box index
    Column("longitude", Float, nullable=False),  # WGS84 — bounding-box index
    Column("utm_x", Float, nullable=False),  # EPSG:25830 easting (metres)
    Column("utm_y", Float, nullable=False),  # EPSG:25830 northing (metres)
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
