## MODIFIED Requirements

### Requirement: Vehicle cards list all user vehicles
Below the map the system SHALL render one card per vehicle belonging to the authenticated user. Each card SHALL display:
- `display_name` and `brand` badge
- `license_plate` (localised label) if set, or a localised "no plate" placeholder if null
- Brand-specific config section (see vehicle-detail spec for what is shown)
- Last known location as coordinates (lat, lon) if available, or a localised "no location" placeholder if not. This line is plain text, not clickable.
- A "View history" button, shown alongside the location line, that opens a `VehicleLocationHistoryModal` scoped to that vehicle (see vehicle-location-history-ui spec). The button SHALL only be shown/enabled when the vehicle has a known location.
- Action buttons: Edit and Delete (labels localised)

#### Scenario: Vehicle card shows Toyota config
- **WHEN** the vehicle is brand TOYOTA
- **THEN** the card shows `username`, `locale`, `vin` and a masked password field (`●●●●●●●●`)

#### Scenario: Vehicle card shows Generic config
- **WHEN** the vehicle is brand GENERIC
- **THEN** the card shows the constructed push URL: `<window.location.origin>/api/vehicles/{location_token}/location`

#### Scenario: Vehicle card shows license plate when set
- **WHEN** a vehicle has a `license_plate` value
- **THEN** the card displays the plate with a localised label (e.g. "License plate: 1234 ABC")

#### Scenario: Vehicle card shows placeholder when no plate
- **WHEN** a vehicle has `license_plate: null`
- **THEN** the card displays a localised placeholder (e.g. "No license plate" / "Sin matrícula")

#### Scenario: Card shows coordinates when location is available
- **WHEN** the vehicle has a last known location
- **THEN** the card displays latitude and longitude to 6 decimal places, and a "View history" button is shown next to it

#### Scenario: Card shows localised placeholder when no location
- **WHEN** the vehicle has no location history
- **THEN** the card displays a localised placeholder string (e.g. "No location data" in English, "Sin datos de ubicación" in Spanish), and no "View history" button is shown

#### Scenario: Clicking "View history" opens the history modal
- **WHEN** a user clicks the "View history" button on a card whose vehicle has a location
- **THEN** the `VehicleLocationHistoryModal` opens scoped to that vehicle
