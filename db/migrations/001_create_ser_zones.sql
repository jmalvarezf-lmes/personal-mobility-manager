-- Migration: 001_create_ser_zones
-- Creates the ser_zones table for storing Madrid SER parking zone data.

CREATE TABLE IF NOT EXISTS ser_zones (
    id           SERIAL PRIMARY KEY,
    street_name  TEXT NOT NULL,
    zone_code    TEXT NOT NULL,
    zone_label   TEXT NOT NULL,
    latitude     DOUBLE PRECISION NOT NULL,  -- WGS84 latitude (bounding-box index)
    longitude    DOUBLE PRECISION NOT NULL,  -- WGS84 longitude (bounding-box index)
    utm_x        DOUBLE PRECISION NOT NULL,  -- EPSG:25830 easting (metres, Euclidean distance)
    utm_y        DOUBLE PRECISION NOT NULL   -- EPSG:25830 northing (metres, Euclidean distance)
);

CREATE INDEX IF NOT EXISTS idx_ser_zones_coords ON ser_zones (latitude, longitude);
