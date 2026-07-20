## ADDED Requirements

### Requirement: Location history modal opens from a vehicle card
Clicking the location line on a `VehicleCard` SHALL open a `VehicleLocationHistoryModal` scoped to that vehicle. The modal SHALL NOT include a vehicle selector — the vehicle is fixed to the card that triggered it. Closing the modal SHALL discard its loaded state (a subsequent open starts from the first page again).

#### Scenario: Clicking the location line opens the modal
- **WHEN** a user clicks the location text on a vehicle card that has at least one recorded location
- **THEN** `VehicleLocationHistoryModal` opens for that vehicle and loads the first page of history

#### Scenario: No selector is present
- **WHEN** the modal is open
- **THEN** no vehicle-switching control is rendered inside it

#### Scenario: Reopening starts fresh
- **WHEN** a user closes the modal after loading two pages, then reopens it for the same vehicle
- **THEN** the modal loads only the first page again, not the previously accumulated pages

---

### Requirement: Modal shows a map with connected, click-to-reveal pins
The modal SHALL render a small Leaflet map containing one pin per currently loaded location. Pins SHALL be connected by a polyline drawn in chronological order (oldest to newest), regardless of the order locations are listed in. The newest loaded location SHALL be rendered with a visually distinct marker from older locations. Clicking any pin SHALL open a popup showing that location's `recorded_at` timestamp.

#### Scenario: Pins connected chronologically
- **WHEN** the modal has loaded locations recorded at times T1 < T2 < T3
- **THEN** the polyline connects the pins in the order T1 → T2 → T3, independent of API response order

#### Scenario: Newest pin is visually distinct
- **WHEN** the modal has loaded at least one page of locations
- **THEN** the pin for the most recently recorded location uses a different icon or color than older pins

#### Scenario: Clicking a pin shows its timestamp
- **WHEN** a user clicks any pin on the history map
- **THEN** a popup opens showing that specific location's `recorded_at` value

---

### Requirement: Modal shows a paired list with load-more pagination
Below the map, the modal SHALL render a list of the same loaded locations, newest first, each row showing its `recorded_at` timestamp and coordinates. The modal SHALL default to loading 5 locations and SHALL provide a "Load more" control that fetches and appends the next 5 (or fewer, if exhausted). When no further locations remain, the "Load more" control SHALL be hidden or disabled.

#### Scenario: Initial load shows up to 5 entries
- **WHEN** the modal opens for a vehicle with more than 5 recorded locations
- **THEN** the list shows the 5 most recent entries and a "Load more" control is visible

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
