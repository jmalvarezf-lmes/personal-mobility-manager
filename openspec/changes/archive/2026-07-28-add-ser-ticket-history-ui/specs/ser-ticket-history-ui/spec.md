## ADDED Requirements

### Requirement: SER ticket history modal opens from a vehicle card button, shown only when tickets exist
A "View SER tickets" button on a `VehicleCard` SHALL open a `VehicleSerTicketHistoryModal` scoped to that vehicle. The button SHALL be rendered only when the vehicle's `has_ser_tickets` field is `true` — i.e. the vehicle has at least one ticket, whether auto-created or manually created; when it is `false`, no button, placeholder, or disabled control SHALL be rendered in its place. The modal SHALL NOT include a vehicle selector — the vehicle is fixed to the card that triggered it. Closing the modal SHALL discard its loaded state (a subsequent open starts from the first page again).

#### Scenario: Button shown when the vehicle has any ticket
- **WHEN** a `VehicleCard` renders for a vehicle whose `has_ser_tickets` is `true`
- **THEN** the "View SER tickets" button is rendered on that card

#### Scenario: Button shown for a vehicle with only manually created tickets
- **WHEN** a `VehicleCard` renders for a vehicle whose only `ParkingTicket` rows have `auto_created=false`, so `has_ser_tickets` is `true`
- **THEN** the "View SER tickets" button is rendered on that card

#### Scenario: Button hidden when the vehicle has no tickets at all
- **WHEN** a `VehicleCard` renders for a vehicle whose `has_ser_tickets` is `false`
- **THEN** no "View SER tickets" button (or any placeholder for it) is rendered on that card

#### Scenario: Clicking the button opens the modal
- **WHEN** a user clicks the "View SER tickets" button on a vehicle card
- **THEN** `VehicleSerTicketHistoryModal` opens for that vehicle and loads the first page of tickets

#### Scenario: No selector is present
- **WHEN** the modal is open
- **THEN** no vehicle-switching control is rendered inside it

#### Scenario: Reopening starts fresh
- **WHEN** a user closes the modal after loading two pages, then reopens it for the same vehicle
- **THEN** the modal loads only the first page again, not the previously accumulated pages

---

### Requirement: Each ticket renders a single-marker map with no path or direction arrows, when coordinates are known
For each loaded SER ticket that has non-null `latitude`/`longitude`, the modal SHALL render a small Leaflet map centered on that ticket's coordinates, showing exactly one marker at `(latitude, longitude)`. The map SHALL NOT render a polyline, and SHALL NOT render any directional arrow — a single parked ticket has no associated movement to visualize. The map's tile layer, container sizing, and marker styling SHALL be visually consistent with `VehicleLocationHistoryModal`'s map. For a ticket with `latitude`/`longitude` both `null` (only possible for tickets persisted before these fields existed), the modal SHALL omit the map for that entry and still render its other details, rather than rendering a marker at a default coordinate or hiding the entry entirely.

#### Scenario: Single marker, no path
- **WHEN** a ticket with `latitude=40.4, longitude=-3.7` is rendered
- **THEN** the map shows exactly one marker at that coordinate, with no polyline and no arrow icon anywhere on the map

#### Scenario: Map is visually consistent with location history's map
- **WHEN** the SER ticket map and the location history map are both rendered
- **THEN** both use the same tile layer, map container sizing, and base marker styling

#### Scenario: Ticket with no stored coordinates omits the map
- **WHEN** a ticket has `latitude=null` and `longitude=null`
- **THEN** the modal renders that ticket's other details (dates, city, zone, auto/manual label) without a map

---

### Requirement: Ticket details show start date, end date, city, zone, and creation provenance
Alongside each ticket's map (when present), the modal SHALL display the ticket's `start_date` and `end_date` (each formatted in the resolved display timezone, per the same resolution rule as `VehicleLocationHistoryModal`'s timestamps: saved preference, else browser timezone, else UTC, with a zone abbreviation suffix), its `city_name` (falling back to `city_code`, or a localized "unknown" placeholder if both are absent), its `zone_number`, and a label reflecting `auto_created`: a localized "Automatic" label when `true`, a localized "Manual" label when `false`, and a distinct localized "Unknown" label when `auto_created` is `null`.

#### Scenario: Ticket with a resolved city name
- **WHEN** a ticket has `city_name="Madrid"` and `zone_number="3"`
- **THEN** the modal shows "Madrid" and "3" alongside that ticket's map

#### Scenario: Ticket with no resolved city name falls back to city code
- **WHEN** a ticket has `city_name=null` and `city_code="MAD"`
- **THEN** the modal shows "MAD" as the city value

#### Scenario: Ticket with neither city name nor code shows a localized placeholder
- **WHEN** a ticket has `city_name=null` and `city_code=null`
- **THEN** the modal shows a localized "unknown" placeholder instead of a blank value

#### Scenario: Dates are formatted in the resolved display timezone
- **WHEN** a ticket's `start_date` and `end_date` are UTC datetimes and the resolved display timezone is `Europe/Madrid`
- **THEN** both dates are shown in `Europe/Madrid` local time with that zone's abbreviation for each date's own instant

#### Scenario: Auto-created ticket shows the automatic label
- **WHEN** a ticket has `auto_created=true`
- **THEN** the modal shows the localized "Automatic" label for that ticket

#### Scenario: Manually created ticket shows the manual label
- **WHEN** a ticket has `auto_created=false`
- **THEN** the modal shows the localized "Manual" label for that ticket

#### Scenario: Pre-existing ticket shows the unknown-provenance label
- **WHEN** a ticket has `auto_created=null`
- **THEN** the modal shows a localized "Unknown" label distinct from both "Automatic" and "Manual"

---

### Requirement: Modal shows a paginated list of tickets with load-more pagination
The modal SHALL default to loading 5 tickets and SHALL provide a "Load more" control that fetches and appends the next 5 (or fewer, if exhausted). When no further tickets remain, the "Load more" control SHALL be hidden or disabled. The list includes every ticket for the vehicle, not only auto-created ones.

#### Scenario: Initial load shows up to 5 entries
- **WHEN** the modal opens for a vehicle with more than 5 tickets
- **THEN** the list shows the 5 most recent tickets and a "Load more" control is visible

#### Scenario: Load more appends without replacing
- **WHEN** a user clicks "Load more"
- **THEN** the next page of tickets is appended, and previously loaded entries (including their maps) remain visible

#### Scenario: Exhausted history hides load more
- **WHEN** a user has loaded all available tickets for a vehicle
- **THEN** the "Load more" control is no longer shown

#### Scenario: Vehicle with fewer than 5 tickets
- **WHEN** the modal opens for a vehicle with 2 tickets
- **THEN** the list shows both entries and no "Load more" control is shown

#### Scenario: List mixes auto-created and manual tickets
- **WHEN** the modal opens for a vehicle with both auto-created and manually created tickets
- **THEN** all of them appear in the same newest-first list, each with its own auto/manual/unknown label

---

### Requirement: SER ticket history UI strings are fully localized
Every user-facing string introduced by this feature — the button label, modal title, empty/loading/error states, field labels (start date, end date, city, zone), and the auto/manual/unknown provenance labels — SHALL be added as translation keys in both `en` and `es` locale files, following the existing `modal.<feature>.*` and `vehicle.*` key naming convention.

#### Scenario: English locale renders English strings
- **WHEN** the active locale is `en`
- **THEN** the button label, modal title, field labels, and provenance labels render in English

#### Scenario: Spanish locale renders Spanish strings
- **WHEN** the active locale is `es`
- **THEN** the button label, modal title, field labels, and provenance labels render in Spanish

#### Scenario: No missing translation keys
- **WHEN** the modal or its button render in either supported locale
- **THEN** no raw translation key (e.g. `modal.serTickets.title`) is shown as literal text in place of translated content
