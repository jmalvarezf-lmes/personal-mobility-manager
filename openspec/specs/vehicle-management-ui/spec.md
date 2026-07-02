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
- Brand-specific config section (see vehicle-detail spec for what is shown)
- Last known location as coordinates (lat, lon) if available, or a localised "no location" placeholder if not
- Action buttons: Edit and Delete (labels localised)

#### Scenario: Vehicle card shows Toyota config
- **WHEN** the vehicle is brand TOYOTA
- **THEN** the card shows `username`, `locale`, `vin` and a masked password field (`●●●●●●●●`)

#### Scenario: Vehicle card shows Generic config
- **WHEN** the vehicle is brand GENERIC
- **THEN** the card shows the constructed push URL: `<window.location.origin>/api/vehicles/{location_token}/location`

#### Scenario: Card shows coordinates when location is available
- **WHEN** the vehicle has a last known location
- **THEN** the card displays latitude and longitude to 6 decimal places

#### Scenario: Card shows localised placeholder when no location
- **WHEN** the vehicle has no location history
- **THEN** the card displays a localised placeholder string (e.g. "No location data" in English, "Sin datos de ubicación" in Spanish)

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

### Requirement: Edit Vehicle opens a pre-filled edit form
Clicking Edit on a vehicle card SHALL open an edit modal pre-filled with the current vehicle's editable fields. For Toyota: display_name, username, locale (password field empty — submitting blank means "keep existing"). For Generic: display_name only. On successful update the card SHALL reflect the new values.

#### Scenario: Edit Toyota vehicle — change display_name only
- **WHEN** the user opens the edit modal for a Toyota vehicle, changes only display_name, and submits
- **THEN** a PUT /api/vehicles/{id} request is sent with the new display_name and empty password
- **THEN** the card updates to show the new display_name

#### Scenario: Edit Toyota vehicle — update credentials
- **WHEN** the user enters a new password in the edit modal and submits
- **THEN** the PUT request includes the new password and the backend updates the encrypted config

#### Scenario: Edit Generic vehicle — only display_name available
- **WHEN** the user opens the edit modal for a Generic vehicle
- **THEN** only the display_name field is editable; no credential fields are shown

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
