## Context

The current system fetches the Madrid Callejero address registry (200075) to infer SER zone membership. This was a workaround: the callejero covers all city addresses with a numeric zone code, but has no colour. Colour is what drives pricing. The 218228 SER Calles dataset is the authoritative source — every row is a real parking spot with its colour, spot count, and UTM coordinates already in metres. Replacing the source also creates the right moment to introduce a city-agnostic provider abstraction, since the current code hard-codes Madrid-specific column names and transformation logic throughout the ingestion stack.

## Goals / Non-Goals

**Goals:**
- Replace 200075 callejero CSV with 218228 SER Calles CSV as the Madrid data source
- Surface zone type (`zone_type`) and spot count in the domain entity, DB, and API
- Introduce `CityParkingDataProvider` port to decouple ingestion from Madrid-specific logic
- Keep the existing truncate-reload ingestion strategy (no incremental complexity)
- Minimal DB migration: add `zone_type` + `spot_count`, drop `zone_label`

**Non-Goals:**
- Adding a second city's provider (Madrid is the only implementation)
- Pricing calculation logic (colour surfacing is sufficient for now)
- Incremental/delta ingestion
- Exposing `bateria_linea` (parking orientation) in the API — parsed but not stored

## Decisions

### D1 — `CityParkingDataProvider` port: single-method interface

**Chosen**: One method `get_records() -> list[ParkingSpotRecord]` that owns the full fetch-and-parse pipeline.

**Why**: Different cities might use REST APIs, FTP files, or proprietary feeds — splitting into `fetch()` + `parse()` would force a common intermediate format that may not make sense for every source. Keeping the pipeline opaque behind one method gives each provider full control.

**Alternative considered**: Two-method interface (`fetch() -> bytes`, `parse(raw) -> list`) — rejected because it leaks the assumption that all sources are text/bytes files.

---

### D2 — `ParkingSpotRecord` replaces `SerZoneRecord`

**Chosen**: Rename the internal value object to `ParkingSpotRecord` with fields: `street_name`, `zone_type`, `latitude`, `longitude`, `utm_x`, `utm_y`, `spot_count`. Drop `zone_code` and `zone_label`.

**Why**: The new source has no numeric zone code — zone type IS the classification identifier. Carrying `zone_code` forward would require inventing a value that doesn't exist in the source file. `ParkingSpotRecord` is also a more accurate name for what the record represents.

**Alternative considered**: Keep `SerZoneRecord` with `zone_code = zone_type` — rejected; it confuses the semantics and perpetuates a naming fiction.

---

### D3 — `CityParkingDataProvider` lives in the domain ports layer

**Chosen**: `src/mobility_manager/domain/ports/city_parking_data_provider.py` — an ABC with `city_code: str` (abstract property) and `get_records() -> list[ParkingSpotRecord]` (abstract method).

**Why**: The port is a domain contract, not an infrastructure detail. Use cases and the scheduler depend on it via dependency injection; concrete providers live in infrastructure.

**Alternative considered**: Put the port in application layer — rejected; it belongs closer to the domain since `ParkingSpotRecord` is a domain value object.

---

### D4 — Zone type parsing: strip RGB prefix, validate via ZoneType subclass

**Chosen**: The `color` CSV column format is `"043000255 Azul"` (9-digit RGB string + space + name). Extract the name with `color_field.split(" ", 1)[1]` after stripping, then pass it to `MadridZoneType.from_raw()` for validation. The resulting `ZoneType` instance's `display_name` is what gets stored — e.g., `"Azul"`. The raw CSV column is still called `color` in the source file; the domain field is `zone_type`.

**Why**: The extracted name is the meaningful zone classification; the RGB prefix is a rendering artifact of the source system. Naming the domain field `zone_type` (rather than `color`) makes the concept city-agnostic — a future city might classify zones by letter codes or names that have nothing to do with colour.

---

### D5 — `bateria_linea` (parking orientation) parsed but not stored

**Chosen**: Parse `bateria_linea` from the CSV but do not add it to `ParkingSpotRecord` or the DB schema in this change.

**Why**: The current use case is SER zone lookup and pricing colour — orientation is not needed. Adding unused columns now complicates the migration with no consumer.

**When to revisit**: When a navigation or parking guidance feature needs to know spot orientation.

---

### D6 — DB migration: additive columns + drop zone_label

**Chosen**: Alembic migration that adds `zone_type VARCHAR(50) NOT NULL DEFAULT ''`, adds `spot_count INTEGER NOT NULL DEFAULT -1`, and drops `zone_label`. The `zone_code` column is also dropped since it has no equivalent in the new source.

**Why**: The ingestion strategy is truncate-reload — the table is always empty before insert. Temporary defaults in the migration satisfy the NOT NULL constraint for the DDL itself without requiring a data backfill. `DEFAULT -1` for `spot_count` reflects the sentinel value for unknown spot counts (0 would be ambiguous — it could mean zero spots were recorded, which is different from the data being absent).

**Rollback**: Drop `zone_type` + `spot_count`, re-add `zone_label` + `zone_code`. The next ingestion run will re-populate from the old source if `MADRID_SER_CALLES_URL` is reverted.

---

### D7 — Dataset URL always resolved from env var

**Chosen**: `MadridSerCallesProvider` reads `MADRID_SER_CALLES_URL` from the environment at construction time. A sensible default is provided so local development works without manual env setup, but the env var is the authoritative source and can be changed without a code deploy.

**Why**: The Madrid Open Data portal can republish datasets at new URLs. If the URL were hardcoded, a URL change would require a code change, a PR, and a deployment cycle. With env var resolution the URL can be updated in the deployment config immediately.

---

### D8 — ZoneType as a domain abstract class; city-specific subclasses enumerate valid types

**Chosen**: A `ZoneType` abstract base class lives in `domain/value_objects/zone_type.py` and declares two abstract members: a `display_name: str` property (the string stored in DB and returned in the API) and a `from_raw(cls, raw: str) -> ZoneType | None` classmethod (parses the source value, returns `None` for unrecognised values). Each city provides a concrete subclass — e.g., `MadridZoneType(ZoneType, str, Enum)` with members `Azul`, `Verde`, `AltaRotacion`, `Naranja`, `Rojo`. The provider calls `MadridZoneType.from_raw(extracted_name)` during parsing; rows where it returns `None` are skipped. `ParkingSpotRecord.zone_type` and `SerZone.zone_type` are typed as `str` (the `display_name` value) — the abstract class is used at the provider level for parsing and validation, not as a field type throughout the stack.

**Why**: An abstract class (rather than a plain enum or a shared cross-city enum) forces every new city to explicitly implement the parsing contract (`from_raw`) and the storage representation (`display_name`). The concept is "zone type classification", not "colour" — a future city might use letter codes, numeric tiers, or names that have nothing to do with colour. Keeping the domain field as `str` avoids circular imports between domain and infrastructure (city-specific subclasses live in infrastructure).

**Alternative considered**: A single shared `ZoneType` enum in the domain covering all cities — rejected; it would couple every city's zone types into one central type, requiring a core domain change every time a new city is added.

**Alternative considered**: `ParkingSpotRecord.zone_type: ZoneType` (typed as the abstract class) — rejected; it would require the repository to reconstruct the city-specific subclass when reading from the DB, which the repository cannot do without knowing the city context at read time.

---

### D9 — Provider registry: env-var-driven city list

**Chosen**: An `ENABLED_CITIES` environment variable (default: `madrid`) lists which provider IDs to activate. The scheduler instantiates each registered provider at startup and runs them on the same interval.

**Why**: Simple, stateless, and deployable without code changes. Adding a city means registering a new provider class and listing its ID in env config.

**Alternative considered**: Auto-discover all subclasses of `CityParkingDataProvider` — rejected; implicit discovery makes it harder to control which providers run in production.

---

## Risks / Trade-offs

- **Breaking API change** → `zone_label` and `zone_code` removed from response, `zone_type` and `spot_count` added. No versioning strategy exists yet; existing consumers must update.
  - *Mitigation*: Document breaking change in PR description; accept for now given early stage.

- **Coordinate system assumption** → 218228 coordinates are assumed to be EPSG:25830 metres based on value range (437,000–445,000 / 4,470,000–4,475,000). If the CRS ever changes in a future dataset publication, the bounding box query and distance calculation will silently produce wrong results.
  - *Mitigation*: Add a startup validation check that spot-tests a known Madrid coordinate against the expected WGS84 bounding box after reprojection.

- **34,519 rows vs larger callejero** → The new file covers only actual SER spots. Points far from any parking spot will still return a nearest result, but with a larger distance. This is semantically correct (the callejero included non-parking addresses which inflated coverage artificially).
  - *Mitigation*: No change needed; the bounding box + expansion retry handles sparsely covered areas.

- **Colour string encoding** → The source uses "Alta Rotación" with a Unicode accent. Latin-1 decoding (already in use) handles this correctly; UTF-8 decoding would also work since this file appears to be UTF-8. Verify encoding on first ingest.

## Migration Plan

1. Apply Alembic migration (adds columns, drops zone_label and zone_code)
2. Deploy new application (new parser, new env var, new API response)
3. First scheduled ingest populates `zone_type` and `spot_count` for all rows
4. Set `MADRID_SER_CALLES_URL` in production (or rely on new default)
5. Update any API consumers expecting `zone_label` / `zone_code` fields

**Rollback**: Revert application deploy + run inverse Alembic migration. No data loss since truncate-reload rebuilds the table on every ingest.
