"""
Shared SQLAlchemy table definitions.

This is the single source of truth for all table schemas. Both repository
implementations and Alembic's env.py import from here so autogenerate
can discover every table in one place.
"""
from sqlalchemy import Column, Float, Integer, MetaData, String, Table, Text

metadata = MetaData()

ser_zones_table = Table(
    "ser_zones",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("street_name", Text, nullable=False),
    Column("zone_type", String(50), nullable=False),
    Column("spot_count", Integer, nullable=False, server_default="-1"),
    Column("latitude", Float, nullable=False),    # WGS84 — bounding-box index
    Column("longitude", Float, nullable=False),   # WGS84 — bounding-box index
    Column("utm_x", Float, nullable=False),       # EPSG:25830 easting (metres)
    Column("utm_y", Float, nullable=False),       # EPSG:25830 northing (metres)
)
