## Context

`find_containing()` has two independent callers reaching it through different paths:

```
SerTicketTriggerHandler (notification)
        │
        ▼
FindContainingSerZone.execute()
        │
        ▼
SerZoneRepository.find_containing(location)  ◄── PORT
        │                                          ▲
        ▼                                          │
PostgresSerZoneRepository.find_containing()  ───────┘
        │                                    ElParkingSerTicketProvider.create_ticket()
        ▼                                    (calls the repo directly, bypassing
   zone.contains(location)                    FindContainingSerZone entirely)
   [SerZone.contains(), domain]
```

Only `PostgresSerZoneRepository.find_containing()` is common to both. A fix applied at `FindContainingSerZone` (application layer) would silently miss the ElParking ticket-creation path. Applying it at the repository is also consistent with existing precedent: `mobility_manager.config` (env-var reader) is already imported directly by several infrastructure classes (`elparking/provider.py`, `telegram/channel.py`, `db.py`, `telegram_link.py`), so a repository reading a config getter directly is idiomatic here, not a layering violation.

Root cause confirmed against live data: a GPS fix landed 0.0368m outside a zone's stored polygon. `SerZone.contains()` uses `geometry.covers(point)`, which has no tolerance — the polygon itself is already buffered generously to absorb GPS error (see `add-ser-zone-boundaries` design.md D4: "GPS positioning error routinely exceeds several metres"), but the point-in-polygon check that consumes it has none.

## Goals / Non-Goals

**Goals:**
- `find_containing()` treats a location within a configurable distance of a zone's polygon boundary as contained, for both of its callers, with a single change point.
- The tolerance is an operator-tunable environment variable, not a user-facing preference (it's a technical/precision knob, not a per-user setting).
- Zero behavior change for any caller that doesn't opt into a tolerance (default parameter preserves exact current semantics).

**Non-Goals:**
- Disambiguating which zone wins when a tolerant point matches more than one (e.g. two adjacent/different-coloured zones near a shared frontier). `find_containing()` keeps returning the first match in `list_all()`'s existing `ORDER BY zone_number, zone_type` — this ambiguity already exists today at zero tolerance for zones that literally share a boundary; widening the tolerance makes it marginally more likely to matter, but resolving it is deferred to a future change.
- Gating `ElParkingSerTicketProvider.create_ticket()` (or any future automatic ticket-creation trigger) on `DetermineSerTicketRequirement` (exemption + enforcement calendar). Confirmed during exploration: today's `POST /parking/ser-tickets` is a documented manual/testing surface (`add-elparking-ticket-creation` design.md), not the production auto-creation trigger, and no automatic trigger exists yet — `auto_create_ticket` has no other reference in the codebase. This tolerance change makes the existing manual endpoint and the future automatic trigger both more GPS-error-tolerant, but does not add or change any exemption/schedule checks.
- Changing `find_nearest()` or the `/parking/ser-zone` `distance_meters` response — unaffected by this change.

## Decisions

### D1 — Apply tolerance inside `PostgresSerZoneRepository.find_containing()`, not in `FindContainingSerZone`
**Chosen**: The repository resolves the configured tolerance and passes it to `zone.contains(location, tolerance_m=...)` for every zone it checks.
**Why**: The single shared code path both consumers (`SerTicketTriggerHandler` and `ElParkingSerTicketProvider`) go through. Fixing it in the application-layer use case would leave the ElParking path on the old strict behavior.
**Alternative considered**: Add `tolerance_m` to the `SerZoneRepository.find_containing()` port signature and have every caller pass it explicitly. Rejected — requires touching both call sites and their tests for no behavioral benefit over resolving it once inside the one shared implementation; the port stays simpler.

### D2 — `SerZone.contains()` gains an optional `tolerance_m: float = 0.0` parameter; stays boundary-inclusive-or-within-tolerance
**Chosen**:
```python
def contains(self, location: GeoLocation, tolerance_m: float = 0.0) -> bool:
    point = Point(*_wgs84_to_utm.transform(location.lng, location.lat))
    return self.geometry.covers(point) or self.geometry.distance(point) <= tolerance_m
```
**Why**: `geometry.distance(point) <= tolerance_m` is mathematically sufficient on its own (distance is exactly 0 for any covered point), but keeping the explicit `covers()` check first preserves the exact existing code path for the zero-tolerance case (no behavior change for existing callers/tests) and is a one-line, low-risk diff over already-tested logic. Default `tolerance_m=0.0` means domain unit tests and any other caller that doesn't pass a tolerance keep byte-for-byte identical behavior.
**Alternative considered**: `geometry.buffer(tolerance_m).covers(point)` — rejected: buffering a dissolved zone polygon (some zones have thousands of vertices, per `add-ser-zone-boundaries` design.md D10) on every containment check is unnecessary work compared to a plain `distance()` call, which is already used elsewhere in this repository (`find_nearest()`).

### D3 — Tolerance configured as an integer environment variable in centimetres, converted to metres at the repository
**Chosen**: `config.py` adds:
```python
def get_ser_zone_containment_tolerance_cm() -> int:
    raw = os.environ.get("SER_ZONE_CONTAINMENT_TOLERANCE_CM", "50")
    try:
        return int(raw)
    except ValueError:
        return 50
```
`PostgresSerZoneRepository.find_containing()` converts: `tolerance_m = get_ser_zone_containment_tolerance_cm() / 100`.
**Why**: Explicit user decision — this is a technical/operational tuning knob, not a per-user preference (avoids adding UI/preference-storage complexity for a value only an operator should tune), and integer centimetres avoids float-parsing env values. Mirrors this file's existing int-with-fallback getters (e.g. `get_vehicle_poll_interval_minutes()`). The conversion to metres happens at the one place that needs metres (the UTM-projected geometry comparison); `SerZone.contains()`'s domain math never needs to know the config value's unit was centimetres.
**Alternative considered**: Store/pass the tolerance in metres as a float end-to-end. Rejected per explicit preference for integer centimetres in the env var.

## Risks / Trade-offs

- **[Risk] Widening containment tolerance also widens `ElParkingSerTicketProvider.create_ticket()`'s zone resolution** — a vehicle whose GPS fix is up to the configured tolerance outside a zone can now have a real (paid) SER ticket created for that zone via the manual endpoint. → Mitigation: this is the explicit intent (confirmed during exploration — the tolerance is meant to apply uniformly to both consumers); the default (50cm) is small relative to typical GPS error and the zone polygon's own buffer margin, and no automatic trigger exists yet to act on this without a human/API call requesting a ticket.
- **[Risk] Frontier ambiguity between adjacent/differently-coloured zones becomes marginally more likely** with a wider tolerance, and `find_containing()` has no explicit tie-break — see Non-Goals. → Mitigation: deferred; flagged as a known limitation, not addressed here.
- **[Trade-off] Tolerance is a single global value, not per-zone or per-city** — simplest possible knob, matches how GPS error is a property of the ingesting device, not the zone. If a future need arises for per-city tuning, `get_ser_zone_containment_tolerance_cm()` is the single seam to extend.
