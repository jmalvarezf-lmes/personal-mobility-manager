## MODIFIED Requirements

### Requirement: Zone boundaries are rendered as polygons with their canonical colour
The map page SHALL fetch all zones from `GET /parking/ser-zones?city=madrid` and render each as a filled polygon shape (via `react-leaflet`'s `GeoJSON`/`Polygon`) using the zone's `colour` field as the fill and stroke colour.

#### Scenario: Blue zone renders as blue polygon
- **WHEN** a zone with `zone_type: "Azul"` and `colour: "#2563EB"` is in the response
- **THEN** a polygon with fill colour `#2563EB` is rendered using the zone's `geometry`

#### Scenario: Grey polygon for unknown zone type
- **WHEN** a zone with `colour: "#6B7280"` is in the response
- **THEN** a polygon with fill colour `#6B7280` is rendered using the zone's `geometry`

#### Scenario: Multi-part zone renders as multiple polygon pieces
- **WHEN** a zone's `geometry` is a GeoJSON `MultiPolygon`
- **THEN** all constituent polygon parts are rendered as one visually grouped shape sharing the same colour and tooltip

### Requirement: Zone polygons have tooltips showing zone number, district, and spots
Each zone polygon SHALL display a Leaflet tooltip on hover containing the zone's `zone_number`, `district`, and `spot_count`. Street names SHALL NOT be shown in the tooltip — the bulk zones response this page consumes does not include them (see `zones-bulk-query`), and fetching them per-hover would require an extra network call per interaction.

#### Scenario: Tooltip shows correct zone details
- **WHEN** the user hovers over a zone polygon
- **THEN** a tooltip is displayed containing the zone number, district, and spot count for that zone, with no street names and no additional network request

### Requirement: Playwright e2e tests cover the map page
The `frontend/` project SHALL include Playwright end-to-end tests in `frontend/e2e/`. Running `pnpm exec playwright test` SHALL execute the suite. Tests SHALL run against a live stack (backend + postgres reachable). The suite SHALL cover: map container present, at least one zone polygon rendered, and tooltip content visible on interaction.

#### Scenario: Map container is present on load
- **WHEN** Playwright navigates to the map page
- **THEN** an element with the Leaflet map container class is present in the DOM

#### Scenario: Zone polygons appear after data loads
- **WHEN** Playwright navigates to the map page and waits for the zones API response
- **THEN** at least one SVG path element representing a zone polygon is present

#### Scenario: Tooltip shows zone details on polygon interaction
- **WHEN** Playwright clicks or hovers over a visible zone polygon
- **THEN** a tooltip element is visible containing a zone number, a district name, and a spot count number
