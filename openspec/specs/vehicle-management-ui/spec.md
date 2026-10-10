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

### Requirement: Vehicle cards list all vehicles accessible to the user
Below the map the system SHALL render one card per vehicle owned by or shared with the authenticated user. Each card SHALL display:
- `display_name` and `brand` badge
- `license_plate` (localised label) if set, or a localised "no plate" placeholder if null
- Brand-specific config section, visible only to the owner; hidden for sharees
- Last known location as coordinates (lat, lon) if available, or a localised "no location" placeholder if not
- A "View history" button, shown alongside the location line, that opens a `VehicleLocationHistoryModal` scoped to that vehicle. The button SHALL only be shown/enabled when the vehicle has a known location.
- Action buttons conditional on ownership: Edit, Delete, and Share for owners; no owner-only actions for sharees

#### Scenario: Owner card shows config and owner actions
- **WHEN** a card is rendered for a vehicle the user owns
- **THEN** the card shows the brand-specific config section, an Edit button, a Delete button, and a Share button

#### Scenario: Generic owner card shows Set location
- **WHEN** a card is rendered for a GENERIC vehicle the user owns
- **THEN** the card shows a "Set location" button alongside Edit/Delete/Share

#### Scenario: Sharee card hides config and owner actions
- **WHEN** a card is rendered for a vehicle shared with the user
- **THEN** the card does not show the config section, Edit, Delete, Share, or Set location buttons

#### Scenario: Sharee card still shows View history when location exists
- **WHEN** a shared vehicle has a known location
- **THEN** the sharee's card shows the "View history" button

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
Clicking Edit on a vehicle card SHALL open an edit modal pre-filled with the current vehicle's editable fields. Edit SHALL only be available to owners.

#### Scenario: Owner opens edit modal
- **WHEN** the owner clicks Edit
- **THEN** the edit modal opens

#### Scenario: Sharee cannot edit
- **WHEN** a sharee views a vehicle card
- **THEN** no Edit button is present

---

### Requirement: Delete Vehicle requires confirmation
Clicking Delete on a vehicle card SHALL show a confirmation prompt. On confirmation a DELETE /api/vehicles/{id} request SHALL be sent. On success the card SHALL be removed from the list. Delete SHALL only be available to owners.

#### Scenario: Delete with confirmation removes card
- **WHEN** the owner clicks Delete and confirms
- **THEN** DELETE /api/vehicles/{id} is sent and the vehicle card disappears from the list

#### Scenario: Sharee cannot delete
- **WHEN** a sharee views a vehicle card
- **THEN** no Delete button is present

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

## ADDED Requirements

### Requirement: Share Vehicle opens a share management modal
Clicking Share on a vehicle card SHALL open a modal listing current sharees and offering an email input to add a new sharee. The modal SHALL only accept emails of registered users. Adding an already-shared email SHALL be a no-op success. The owner SHALL be able to remove any sharee from the list. The modal SHALL surface API errors inline.

#### Scenario: Owner opens share modal
- **WHEN** the owner clicks Share on a vehicle card
- **THEN** a modal opens showing the current sharee list and an email input

#### Scenario: Owner adds a sharee by email
- **WHEN** the owner enters a registered user's email and submits
- **THEN** `POST /api/vehicles/{id}/shares` is sent
- **THEN** the modal's sharee list is replaced with the response's `sharees` array, which includes the new sharee

#### Scenario: Owner removes a sharee
- **WHEN** the owner clicks Remove next to a sharee
- **THEN** the Remove button is disabled while the request is in flight
- **THEN** `DELETE /api/vehicles/{id}/shares/{user_id}` is sent
- **THEN** the sharee is removed from the list only after the API call succeeds

#### Scenario: Unknown email shows error
- **WHEN** the owner enters an email not present in the system
- **THEN** the modal displays an error and no share is created

#### Scenario: Sharee cannot open share modal
- **WHEN** a sharee views a vehicle card
- **THEN** no Share button is present and the share modal cannot be opened
