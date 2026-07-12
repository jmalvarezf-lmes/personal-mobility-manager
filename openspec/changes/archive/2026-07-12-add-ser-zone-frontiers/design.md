## Context

`add-ser-zone-boundaries` gave `SerZone` real, precise curb-band geometry per `(zone_number, zone_type)` — correct for containment/ticket-liability, but visually illegible as a "zone": a zone number is hundreds of thin, disconnected strips scattered across a district. This change adds a second, presentation-only geometry per `zone_number` — a "frontier" — so the map reads like a real zone map, while the precise strips keep rendering on top for real detail, and containment logic (`SerZone.contains()`) is untouched.

**A first attempt at this was built and discarded.** It computed the frontier via a Voronoi tessellation over all ~34,000 curb-band midpoints city-wide, dissolved and buffer-capped per zone_number. Live testing against the real dataset showed this consuming multiple gigabytes of memory without completing, and it OOM-killed the Docker environment (exit 137) on a real ingestion attempt — a disproportionate cost given the actual goal is just "show a neighbourhood-scale outline." This design replaces that approach entirely with a lookup against Madrid's official administrative boundary data.

**The replacement**: Madrid's Geoportal publishes a "Barrios" (neighbourhood) shapefile — 131 real, pre-drawn, non-overlapping administrative polygons (`https://geoportal.madrid.es/fsdescargas/IDEAM_WBGEOPORTAL/LIMITES_ADMINISTRATIVOS/Barrios/Barrios.zip`), each with a compound `COD_DISB` code (district number + barrio number, e.g. `"1-1"`) and an official `NOMBRE`. Cross-tabulated against the real callejero data: every one of the 66 real SER zone numbers' majority `(district_code, barrio_code)` pair matches an official `COD_DISB` exactly — a 100% exact-code join, no fuzzy string matching.

## Goals / Non-Goals

**Goals:**
- One frontier polygon per `zone_number` (merging all its colours), sourced from a real official neighbourhood boundary — not synthesized
- A neighbourhood name per `zone_number`, using the barrio dataset's own authoritative name — not derived from free-text matching
- Trivially cheap ingestion cost (a lookup against 131 small records, not a city-wide geometric computation)

**Non-Goals:**
- Changing `SerZone.contains()` or any ticket-liability logic — the frontier is presentation-only
- Per-`zone_type` frontier colouring — a single neutral pale grey is used regardless of which colours a zone number contains
- Synthesizing any fallback geometry when a zone_number's code doesn't resolve to a known barrio — skip it, don't approximate

## Decisions

### D1 — Frontier sourced from Madrid's official Barrios shapefile, not synthesized

**Chosen**: Download and parse `Barrios.zip` (SHP format) the same way the SER band shapefile is already parsed (`pyshp`, already a dependency — no new one needed). For each `zone_number`, resolve its frontier by looking up its majority compound code against this dataset's 131 records — a dictionary lookup, not a geometric computation.

**Why**: The discarded Voronoi approach tried to solve "what does zone X's territory look like" by synthesizing an answer from scattered points. That's the wrong question — Madrid already publishes the answer as real, official, pre-drawn boundaries. Using them directly is simpler, cheaper (O(1) lookup vs. a tessellation over 34,000 points), and more correct (crisp, non-overlapping by construction, since these are real administrative boundaries — not an approximation that might overlap a neighbour or sprawl into a park).

**Alternative considered**: Voronoi tessellation plus buffer-cap (the discarded first attempt) — rejected after live testing showed multi-gigabyte memory consumption and an OOM kill on real data, for a problem that turned out to already have an authoritative, free, tiny (~280KB) answer.

---

### D2 — Join by compound code (`district_code-barrio_code`), not by barrio name

**Chosen**: Extend callejero parsing to capture `Codigo de distrito` and `Codigo de barrio` (previously unused numeric codes). For each `zone_number`, compute the majority `(district_code, barrio_code)` pair by matched-address-point count (same majority-vote pattern already used for other per-zone attributes), format it as `f"{district_code}-{barrio_code}"` to match the Barrios shapefile's `COD_DISB` field, and join on that.

**Why**: A name-based join (matching `Nombre del barrio` text against the shapefile's `NOMBRE` field) was tried first and only reached 98.5% (65/66) — the one gap was "El Pilar" (callejero's spelling) vs. "Pilar" (the official name), a spelling-convention mismatch requiring fuzzy normalization (accent stripping, article removal) to paper over. The compound-code join reaches 100% (66/66) with zero string normalization, because it's a genuine foreign-key relationship between two datasets published by the same city GIS system, not a heuristic string match. It also sidesteps SER zone_number itself being usable as a join key: SER zone numbers and barrio codes are independent numbering schemes that only coincidentally overlap for some low values (verified: SER zone 163's official barrio, by code, is "Canillas" — a completely unrelated neighbourhood on the other side of the city from zone 163's real majority barrio, "Sol") — confirming zone_number cannot be used as a shortcut key into this dataset at all; only the compound `district_code-barrio_code` derived from the callejero join works.

**Alternative considered**: Name-based join with normalization (strip accents, strip leading Spanish articles) — rejected in favour of the exact code-based join once it was found; normalization only gets you to parity with something that already has a perfect, simpler answer.

---

### D3 — Official `NOMBRE` is the authoritative neighbourhood name, not the callejero's raw text

**Chosen**: Once a zone_number's compound code resolves against the Barrios shapefile, use that record's own `NOMBRE` field as the `neighbourhood` value — not whatever string the callejero happened to spell it as.

**Why**: One dataset should be the source of truth for the name once the join succeeds. This also means the "El Pilar"/"Pilar" spelling difference discovered in D2 has no user-visible effect: whichever spelling the callejero used, the displayed name is always Madrid's own canonical one.

---

### D4 — `ser_zone_areas` table, keyed by `zone_number` alone (unchanged from the discarded design)

**Chosen**: `ser_zone_areas (zone_number VARCHAR(10) PRIMARY KEY, neighbourhood TEXT NOT NULL, geometry_wkt TEXT NOT NULL)`. Same shape as the discarded attempt — this decision was sound, only what populates it changes.

**Why**: Mirrors the existing `ser_zone_streets` precedent — a concept that doesn't fit the `(zone_number, zone_type)` grain gets its own table keyed at the grain it actually belongs to.

---

### D5 — Unresolvable zone_number is skipped, not given a fallback shape

**Chosen**: If a zone_number's majority compound code doesn't match any Barrios record (shouldn't happen given the 100% match confirmed against real data, but the data could drift over time), skip that zone_number's frontier entirely and log a warning — its precise `ser_zones` geometry and ticket-liability logic are entirely unaffected either way.

**Why**: Consistent with the project's established "skip the bad item, log a warning, keep going" convention (e.g. `list_all()`'s per-row geometry-parse handling). No synthesized fallback is attempted — that was the exact failure mode (an uncapped Voronoi cell) that made the discarded approach's edge cases dangerous; here there's nothing to synthesize, so there's nothing to get wrong.

---

### D6 — Repository access: new port method, not new fields on `SerZone` (unchanged from the discarded design)

**Chosen**: `SerZoneRepository` gains `get_zone_area(zone_number: str) -> ZoneArea | None` and `list_zone_areas() -> list[ZoneArea]`. `CityParkingDataProvider` gains `get_zone_areas() -> list[ZoneArea]` alongside `get_records()`. The existing `SerZone` domain entity and `get_records()`'s contract are unchanged.

**Why**: Mirrors the `get_street_names` precedent — a zone_number-grain concept gets its own accessor rather than being bolted onto the `(zone_number, zone_type)`-grain entity or forcing `IngestSerZones` to know Madrid-specific details directly.

---

### D7 — No caching/lifecycle complexity needed

**Chosen**: `get_zone_areas()` re-downloads and re-parses the Barrios shapefile (and re-derives the compound-code majority vote from the same band/callejero data `get_records()` already processes) on every call, with no cross-call cache.

**Why**: The discarded Voronoi design introduced an instance-level cache to avoid re-computing an expensive pipeline twice per run — and that cache turned into a real bug (it never invalidated across scheduled ingestion runs, silently freezing all Madrid data at whatever the first run fetched). This design has no expensive computation to cache in the first place: parsing a 131-record, ~280KB shapefile and doing a dictionary lookup is cheap enough to simply redo every time, which is also simpler and has no staleness failure mode to get wrong.

---

### D8 — Frontier fill colour: fixed neutral pale grey, not sent by the API (unchanged from the discarded design)

**Chosen**: The frontend applies a single constant pale grey style to every frontier polygon; the API's `frontiers` array carries no colour field.

**Why**: A zone_number's frontier can span multiple SER colours (Azul/Verde/Alta Rotación bands within the same zone_number) — no single colour is correct to assign it.

## Risks / Trade-offs

- **Multiple zone_numbers can share the same barrio** (SER zones subdivide barrios more finely than 1:1 in some districts) → their `frontiers` entries will carry identical geometry. Visually this just means the same pale grey shape draws twice in the same place — harmless, not a rendering bug.
- **The Barrios dataset could change over time** (Madrid redraws barrio boundaries only rarely, but not never) → since it's re-fetched every ingestion run (D7), any such change is picked up automatically at the next scheduled run, consistent with how the other two sources already behave.
- **Zero-records-abort guarantee must extend to this third table too** — the same partial-write class of bug fixed for `ser_zone_areas` in the discarded design's review pass applies identically here: if `get_records()` succeeds but `get_zone_areas()` comes back empty, ingestion must abort before writing anything, not silently truncate `ser_zone_areas`.

## Migration Plan

1. Add `ser_zone_areas` table via Alembic migration (unchanged shape from the discarded attempt)
2. Extend callejero parsing to capture `Codigo de distrito`/`Codigo de barrio`
3. Add a Barrios shapefile download/parse module (mirrors the existing SER band shapefile module)
4. Implement the compound-code majority-vote + lookup step, replacing the discarded Voronoi computation
5. Extend `IngestSerZones`/`MadridSerStreetsProvider` to populate `ser_zone_areas` within the same truncate-reload transaction, with the same zero-records-abort guarantee as the other two tables
6. Add `get_zone_area`/`list_zone_areas` to `SerZoneRepository`
7. Update `GET /parking/ser-zone` (add `neighbourhood`) and `GET /parking/ser-zones` (add `frontiers` array) — additive, non-breaking
8. Update the frontend map to render the new frontier layer

**Rollback**: Revert the application deploy and drop `ser_zone_areas` via the inverse migration. No data-loss risk — truncate-reload means the next ingestion run under whichever code version is active repopulates everything.
