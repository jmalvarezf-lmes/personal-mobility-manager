### Requirement: My Vehicles page is protected and accessible from nav
The system SHALL expose a `/my-vehicles` route rendered by `MyVehiclesPage`. This route SHALL be wrapped in `ProtectedRoute` so unauthenticated users are redirected to `/`. The navigation bar SHALL show a "My Vehicles" link only when a user is authenticated.

#### Scenario: Unauthenticated access redirects to home
- **WHEN** a user who is not logged in navigates to `/my-vehicles`
- **THEN** the app redirects them to `/`

#### Scenario: Authenticated user sees nav link
- **WHEN** a user is logged in
- **THEN** the nav bar displays a "My Vehicles" link alongside the Map link

#### Scenario: Unauthenticated user does not see nav link
- **WHEN** no user is logged in
- **THEN** the nav bar does not display a "My Vehicles" link

---

### Requirement: Page shows a shared map of all vehicle locations
The system SHALL render a single Leaflet map at the top of the My Vehicles page. Vehicles with a known last location SHALL appear on the map as a distinct car icon (DivIcon with a car SVG or emoji, visually distinct from the zone CircleMarkers). The map SHALL fit its bounds to include all visible car markers. If no vehicle has a known location the map SHALL show a default center.

#### Scenario: Vehicles with location appear on map
- **WHEN** the user has vehicles with known last locations
- **THEN** each vehicle is shown on the shared map as a car icon at its last known coordinates

#### Scenario: Map popup shows vehicle name
- **WHEN** the user clicks a car icon on the map
- **THEN** a popup appears showing the vehicle's display_name

#### Scenario: No vehicles with location — map shows default
- **WHEN** no vehicle has a known location
- **THEN** the map renders centered on a default location (e.g. Madrid) with no markers

---

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

---

### Requirement: Add Vehicle opens a brand-discriminated creation form
The page SHALL include an "Add Vehicle" button that opens a modal or inline form. The form SHALL first ask for brand (Toyota or Generic) and then show the appropriate fields. On successful creation the vehicle list SHALL refresh.

#### Scenario: Create Toyota vehicle via form
- **WHEN** the user selects Toyota, fills in display_name, vin, username, password, locale, and submits
- **THEN** a POST /api/vehicles request is sent with the correct payload
- **THEN** the new vehicle appears in the list without a page reload

#### Scenario: Create Generic vehicle via form
- **WHEN** the user selects Generic, fills in display_name, and submits
- **THEN** a POST /api/vehicles request is sent with brand "generic"
- **THEN** the new vehicle card shows the generated push URL

#### Scenario: Creation error shows feedback
- **WHEN** the API returns an error on vehicle creation
- **THEN** the modal displays an inline error message and stays open

---

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

---

### Requirement: Delete Vehicle requires confirmation
Clicking Delete on a vehicle card SHALL show a confirmation prompt (browser confirm dialog or inline confirmation UI). On confirmation a DELETE /api/vehicles/{id} request SHALL be sent. On success the card SHALL be removed from the list.

#### Scenario: Delete with confirmation removes card
- **WHEN** the user clicks Delete and confirms
- **THEN** DELETE /api/vehicles/{id} is sent and the vehicle card disappears from the list

#### Scenario: Delete cancelled leaves vehicle intact
- **WHEN** the user clicks Delete but cancels the confirmation
- **THEN** no DELETE request is sent and the vehicle card remains

#### Scenario: Delete error shows feedback
- **WHEN** the DELETE request returns an error
- **THEN** an error message is displayed and the card remains in the list

---

### Requirement: Generic vehicle cards offer a "Set location" action
Each vehicle card for a `GENERIC` vehicle SHALL show a "Set location" button (localised) alongside the existing Edit/Delete actions. Clicking it SHALL open a `SetVehicleLocationModal` scoped to that vehicle. This button SHALL NOT be shown on Toyota vehicle cards.

#### Scenario: Generic vehicle card shows the action
- **WHEN** a vehicle card is rendered for a `GENERIC` vehicle
- **THEN** a "Set location" button is shown

#### Scenario: Toyota vehicle card does not show the action
- **WHEN** a vehicle card is rendered for a `TOYOTA` vehicle
- **THEN** no "Set location" button is shown

---

### Requirement: Set location dialog offers browser geolocation with manual fallback
The `SetVehicleLocationModal` SHALL present a single form containing a "Use my current location" button and editable latitude/longitude number inputs. Clicking "Use my current location" SHALL invoke the Browser Geolocation API and, on success, populate the latitude/longitude inputs with the returned coordinates while leaving them editable. The same Save action SHALL submit whatever values are currently in the latitude/longitude inputs, regardless of whether they were autofilled or typed manually.

#### Scenario: Geolocation autofills editable fields
- **WHEN** the user clicks "Use my current location" and the browser grants permission
- **THEN** the latitude and longitude inputs are populated with the device's current coordinates
- **THEN** the user can still edit those values before saving

#### Scenario: Geolocation denied falls back to manual entry
- **WHEN** the user clicks "Use my current location" and the browser denies permission or the API errors
- **THEN** an inline error message is shown
- **THEN** the latitude and longitude inputs remain empty and editable for manual entry

#### Scenario: Manual entry without using geolocation
- **WHEN** the user types latitude and longitude values directly without clicking "Use my current location"
- **THEN** the Save button submits those typed values

#### Scenario: Out-of-range coordinates rejected client-side
- **WHEN** the user enters a latitude outside [-90, 90] or a longitude outside [-180, 180]
- **THEN** the form shows a validation error and does not submit

#### Scenario: Successful save closes the dialog and refreshes the card
- **WHEN** the submission succeeds
- **THEN** the modal closes and the vehicle card reflects the newly submitted location

#### Scenario: Save error keeps the dialog open with feedback
- **WHEN** the submission request fails (e.g. HTTP 429 or 500)
- **THEN** the modal displays an inline error message and stays open with the entered values intact
