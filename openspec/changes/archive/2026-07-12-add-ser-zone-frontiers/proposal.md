## Why

The precise curb-band polygons from `add-ser-zone-boundaries` are geometrically correct but visually illegible as "zones" — a SER zone number is a scattered field of thin, disconnected strips across a district (e.g. zone 151 has 936 separate parts covering only 6.6% of its own bounding box). There is also no user-recognizable neighbourhood name — only the coarse city district (e.g. "SALAMANCA").

A first attempt at this solved the wrong problem: synthesizing a smoothed "frontier" shape via a city-wide Voronoi tessellation over all ~34,000 curb-band midpoints, dissolved and buffer-capped per zone_number. That approach was abandoned after live testing showed it consuming multiple gigabytes of memory and never completing — a fundamentally disproportionate cost for what should be a simple lookup, and it OOM-killed the Docker environment (exit 137) on a real ingestion run. Investigating further, Madrid's Geoportal publishes an official "Barrios" (neighbourhood) administrative boundary dataset — 131 real, pre-drawn, non-overlapping polygons — that solves this directly: no synthesis needed, just a lookup.

## What Changes

- Add a new Madrid data source: the official **Barrios** administrative boundary shapefile (131 real neighbourhood polygons, `COD_DISB` compound district-barrio code, `NOMBRE` official name), downloaded from `https://geoportal.madrid.es/fsdescargas/IDEAM_WBGEOPORTAL/LIMITES_ADMINISTRATIVOS/Barrios/Barrios.zip`. Parsed via the existing `pyshp` dependency — no new dependency, reusing the same SHP/DBF parsing pattern already used for the SER band shapefile.
- Extend callejero CSV parsing to capture `Codigo de distrito` and `Codigo de barrio` (previously unused numeric codes, alongside the existing street/district/zone-number fields).
- For each `zone_number`, compute the majority `(district_code, barrio_code)` compound key (by matched-address-point count, the same majority-vote pattern already used and validated for other per-zone attributes) and look up that key directly against the Barrios shapefile's `COD_DISB` field to resolve both the **frontier geometry** (the barrio's real polygon) and the **neighbourhood name** (the barrio's official `NOMBRE` — authoritative, not derived from free-text matching). Confirmed against the real dataset: **100% of zone numbers (66/66)** resolve this way, a genuine exact code-based join, not a fuzzy string match. (A name-based join was also tested and only reached 98.5%, with the one gap being a spelling-convention mismatch the code-based join sidesteps entirely.)
- New `ser_zone_areas` table, keyed by `zone_number` alone: holds the resolved neighbourhood name and frontier geometry (a real barrio boundary, not a synthesized shape). Rendered as a pale grey wash underneath the existing precise, fully-coloured curb strips — both are visible at once. **Containment/ticket-liability logic (`SerZone.contains()`) is unaffected — the frontier is presentation-only**, exactly as before.
- `GET /parking/ser-zone` (single-coordinate lookup) additionally returns the neighbourhood name alongside the existing district.
- `GET /parking/ser-zones` (bulk map endpoint) additionally returns a `frontiers` array (one entry per zone_number: `zone_number`, `neighbourhood`, `geometry`), alongside the existing unchanged `zones` array.
- Frontend renders the new frontier polygons as a pale grey layer beneath the existing precise zone polygons.

**Out of scope**: any change to `SerZone.contains()`/ticket-liability logic; per-zone_type colouring of the frontier (a single neutral style is used for all frontiers, since a zone number can mix SER colours); modelling anything beyond the official barrio boundary (no synthesized/approximated geometry of any kind — if a zone_number's compound code doesn't resolve to a known barrio, that zone_number is skipped with a logged warning, not given a fallback shape).

## Capabilities

### New Capabilities
- `ser-zone-frontier`: the `ser_zone_areas` table, the Barrios-shapefile download/parse, and the compound-code majority-vote lookup that resolves each zone_number's frontier geometry and neighbourhood name.

### Modified Capabilities
- `city-parking-data-provider`: `SerZoneBoundaryRecord` gains a `neighbourhood: str` field; `CityParkingDataProvider` gains a `get_zone_areas() -> list[ZoneArea]` abstract method alongside `get_records()`; `MadridSerStreetsProvider` additionally downloads and parses the Barrios shapefile as a third Madrid source.
- `ser-zone-ingestion`: callejero parsing captures `Codigo de distrito`/`Codigo de barrio` instead of (or alongside) `Nombre del barrio`; ingestion computes and stores `ser_zone_areas` in the same truncate-reload transaction as `ser_zones`/`ser_zone_streets`.
- `ser-zone-query`: `SerZoneRepository` gains `get_zone_area`/`list_zone_areas` methods (mirroring the existing `get_street_names` pattern, not added to the `SerZone` entity itself); `GET /parking/ser-zone`'s response gains `neighbourhood`.
- `zones-bulk-query`: `GET /parking/ser-zones` response gains a `frontiers` array alongside the existing `zones` array.
- `osm-zone-map`: frontend renders the new frontier layer (pale grey, beneath the existing precise polygons); existing precise-zone rendering is unchanged.

## Impact

- Alembic migration: new `ser_zone_areas` table (`zone_number` PK, `neighbourhood TEXT`, `geometry_wkt TEXT`)
- `infrastructure/parking_services/madrid/`: new Barrios shapefile download/parse module; callejero parsing extended to capture district/barrio codes; new compound-code majority-vote + lookup module (replacing the discarded Voronoi computation)
- `domain/value_objects/`: `SerZoneBoundaryRecord` gains `neighbourhood`; new `ZoneArea` value object
- `domain/ports/`: `CityParkingDataProvider` gains `get_zone_areas()`; `SerZoneRepository` gains `get_zone_area`/`list_zone_areas`
- `presentation/api/routers/parking.py`, `zones.py`, `presentation/api/schemas.py`: additive, non-breaking response fields
- `frontend/`: new frontier rendering layer in the map component
- No new dependencies — `pyshp` (already a dependency) parses the Barrios shapefile the same way it parses the SER band shapefile
- New env var: `MADRID_BARRIOS_SHP_URL` (default: the official Geoportal URL above)
