-- Migration: 001_create_ser_zones
-- Creates the ser_zones table for storing Madrid SER parking zone data.

CREATE TABLE IF NOT EXISTS ser_zones (
    id           SERIAL PRIMARY KEY,
    street_name  TEXT NOT NULL,
    zone_code    TEXT NOT NULL,
    zone_label   TEXT NOT NULL,
    latitude     DOUBLE PRECISION NOT NULL,
    longitude    DOUBLE PRECISION NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_ser_zones_coords ON ser_zones (latitude, longitude);
