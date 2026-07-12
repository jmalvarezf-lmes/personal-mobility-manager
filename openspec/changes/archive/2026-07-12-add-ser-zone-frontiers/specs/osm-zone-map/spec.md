## ADDED Requirements

### Requirement: Zone frontiers are rendered as a pale neutral layer beneath the precise zone polygons
The map page SHALL fetch the `frontiers` array from `GET /parking/ser-zones?city=madrid` and render each as a filled polygon shape using a single fixed pale grey style (not derived from any zone's `colour`), drawn beneath the existing precise per-`(zone_number, zone_type)` polygons so both are visible at once.

#### Scenario: Frontier renders in neutral grey regardless of the zone_number's colours
- **WHEN** a zone_number with both Azul and Verde precise zones is rendered
- **THEN** its single frontier entry renders in the same fixed pale grey used for every other frontier, not a colour derived from either zone_type

#### Scenario: Frontier renders beneath precise zone polygons
- **WHEN** both a frontier and its zone_number's precise zone polygons are visible in the same viewport
- **THEN** the precise, fully-coloured polygons render on top of the pale grey frontier, not the other way around

#### Scenario: Frontier tooltip shows the neighbourhood name
- **WHEN** the user hovers over a frontier polygon (in an area not covered by a precise zone polygon)
- **THEN** a tooltip is displayed containing the zone number and neighbourhood name

### Requirement: Playwright e2e tests cover the frontier layer
The Playwright suite in `frontend/e2e/map.spec.ts` SHALL additionally verify that frontier polygons render alongside the existing precise zone polygons.

#### Scenario: Frontier polygons appear after data loads
- **WHEN** Playwright navigates to the map page and waits for the zones API response
- **THEN** at least one frontier polygon element is present, in addition to the existing precise zone polygon assertions
