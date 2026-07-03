## MODIFIED Requirements

### Requirement: Vehicle cards list all user vehicles
Below the map the system SHALL render one card per vehicle belonging to the authenticated user. Each card SHALL display:
- `display_name` and `brand` badge
- `license_plate` (localised label) if set, or a localised "no plate" placeholder if null
- Brand-specific config section (see vehicle-detail spec for what is shown)
- Last known location as coordinates (lat, lon) if available, or a localised "no location" placeholder if not
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
- **THEN** the card displays latitude and longitude to 6 decimal places

#### Scenario: Card shows localised placeholder when no location
- **WHEN** the vehicle has no location history
- **THEN** the card displays a localised placeholder string (e.g. "No location data" in English, "Sin datos de ubicación" in Spanish)

### Requirement: Edit Vehicle opens a pre-filled edit form including license plate
Clicking Edit on a vehicle card SHALL open an edit modal pre-filled with the current vehicle's editable fields. For Toyota: display_name, username, locale, license_plate (password field empty — submitting blank means "keep existing"). For Generic: display_name and license_plate. The license_plate field SHALL be optional (clearable). On successful update the card SHALL reflect the new values including the plate.

#### Scenario: Edit Toyota vehicle — change display_name only
- **WHEN** the user opens the edit modal for a Toyota vehicle, changes only display_name, and submits
- **THEN** a PUT /api/vehicles/{id} request is sent with the new display_name and empty password
- **THEN** the card updates to show the new display_name

#### Scenario: Edit Toyota vehicle — update credentials
- **WHEN** the user enters a new password in the edit modal and submits
- **THEN** the PUT request includes the new password and the backend updates the encrypted config

#### Scenario: Edit Generic vehicle — display_name and license plate available
- **WHEN** the user opens the edit modal for a Generic vehicle
- **THEN** the display_name and license_plate fields are editable; no credential fields are shown

#### Scenario: Edit vehicle — set license plate
- **WHEN** the user enters a license plate in the edit modal and submits
- **THEN** the PUT request includes the license_plate value and the card updates to display it

#### Scenario: Edit vehicle — clear license plate
- **WHEN** the user clears the license plate field in the edit modal and submits
- **THEN** the PUT request sends `license_plate: null` and the card updates to show the "no plate" placeholder
