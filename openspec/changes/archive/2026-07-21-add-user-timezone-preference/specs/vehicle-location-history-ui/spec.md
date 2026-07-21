## MODIFIED Requirements

### Requirement: Modal shows a map with connected, directional, click-to-reveal pins
The modal SHALL render a small Leaflet map containing one pin per currently loaded location. Pins SHALL be connected by a polyline drawn in chronological order (oldest to newest), regardless of the order locations are listed in. Each segment of the polyline (between two chronologically consecutive pins) SHALL display a directional arrow, oriented from the older pin toward the newer pin, so the travel direction of the route is visible without relying on pin order alone. The newest loaded location SHALL be rendered with a visually distinct marker from older locations. Clicking any pin SHALL open a popup showing that location's `recorded_at` timestamp, formatted in the resolved display timezone and suffixed with that zone's abbreviation for the timestamp's own date (see "Displayed timestamps resolve to a display timezone").

#### Scenario: Pins connected chronologically
- **WHEN** the modal has loaded locations recorded at times T1 < T2 < T3
- **THEN** the polyline connects the pins in the order T1 → T2 → T3, independent of API response order

#### Scenario: Each segment shows a direction arrow
- **WHEN** the modal has loaded locations recorded at times T1 < T2 < T3
- **THEN** the map shows an arrow on the T1→T2 segment pointing toward T2, and an arrow on the T2→T3 segment pointing toward T3

#### Scenario: Single location has no segment or arrow
- **WHEN** the modal has loaded exactly one location
- **THEN** the map shows only that one pin, with no polyline and no arrow

#### Scenario: Newest pin is visually distinct
- **WHEN** the modal has loaded at least one page of locations
- **THEN** the pin for the most recently recorded location uses a different icon or color than older pins

#### Scenario: Clicking a pin shows its timestamp in the resolved timezone
- **WHEN** a user clicks any pin on the history map
- **THEN** a popup opens showing that specific location's `recorded_at` value formatted in the resolved display timezone, not raw UTC
- **THEN** the shown value includes that zone's abbreviation for the timestamp's own date (e.g. "14:32 CEST")

---

### Requirement: Modal shows a paired list with load-more pagination
Below the map, the modal SHALL render a list of the same loaded locations, newest first, each row showing its `recorded_at` timestamp — formatted in the resolved display timezone and suffixed with that zone's abbreviation for the row's own date (see "Displayed timestamps resolve to a display timezone") — and coordinates. The modal SHALL default to loading 5 locations and SHALL provide a "Load more" control that fetches and appends the next 5 (or fewer, if exhausted). When no further locations remain, the "Load more" control SHALL be hidden or disabled.

#### Scenario: Initial load shows up to 5 entries
- **WHEN** the modal opens for a vehicle with more than 5 recorded locations
- **THEN** the list shows the 5 most recent entries and a "Load more" control is visible

#### Scenario: List rows show timestamps in the resolved timezone
- **WHEN** the list renders a location recorded at a given UTC instant
- **THEN** the row displays that instant formatted in the resolved display timezone, not the raw UTC ISO string
- **THEN** the row's displayed value includes that zone's abbreviation for the instant's own date (e.g. "14:32 CEST")

#### Scenario: Load more appends without replacing
- **WHEN** a user clicks "Load more"
- **THEN** the next page of locations is appended to both the list and the map (new pins + extended polyline), and previously loaded entries remain visible

#### Scenario: Exhausted history hides load more
- **WHEN** a user has loaded all available locations for a vehicle
- **THEN** the "Load more" control is no longer shown

#### Scenario: Vehicle with fewer than 5 locations
- **WHEN** the modal opens for a vehicle with 2 recorded locations
- **THEN** the list shows both entries and no "Load more" control is shown

#### Scenario: Vehicle with no recorded locations
- **WHEN** the modal opens for a vehicle with zero recorded locations
- **THEN** the modal shows a localised empty-state message instead of a map and list

---

## ADDED Requirements

### Requirement: Displayed timestamps resolve to a display timezone
Every `recorded_at` timestamp shown in `VehicleLocationHistoryModal` (list rows and map pin popups) SHALL be formatted in a display timezone resolved, at render time, as: the user's saved `timezone` preference if set; otherwise the browser's detected timezone (`Intl.DateTimeFormat().resolvedOptions().timeZone`); otherwise `UTC`. The formatted value SHALL be suffixed with the resolved zone's abbreviation (e.g. "CEST"), computed against that specific timestamp's own date — not a single cached abbreviation for the zone — so it reflects whichever offset (standard or daylight saving) applied at that instant. This resolution and formatting SHALL happen entirely client-side — the underlying API response and any internal use of the timestamp (ordering, pagination) SHALL remain unaffected and continue to use raw UTC values.

#### Scenario: User with a saved timezone preference
- **WHEN** the authenticated user's `timezone` preference is `"Europe/Madrid"`
- **THEN** all `recorded_at` timestamps in the modal are formatted using the `Europe/Madrid` zone

#### Scenario: User with no saved preference falls back to the browser's zone
- **WHEN** the authenticated user's `timezone` preference is unset (`null`)
- **THEN** timestamps are formatted using the browser's detected timezone

#### Scenario: Timezone detection is unavailable
- **WHEN** the user's `timezone` preference is unset and the browser's timezone cannot be detected
- **THEN** timestamps are formatted in UTC

#### Scenario: Internal ordering is unaffected
- **WHEN** the modal loads and sorts locations chronologically for the map polyline
- **THEN** the underlying UTC `recorded_at` values are used for ordering, independent of the display timezone used to render the visible label

#### Scenario: Abbreviation reflects the timestamp's own date across a DST boundary
- **WHEN** the modal shows two entries for the `Europe/Madrid` display timezone, one recorded in January and one recorded in July
- **THEN** the January entry's abbreviation is "CET" and the July entry's abbreviation is "CEST", even though both use the same saved/detected zone
