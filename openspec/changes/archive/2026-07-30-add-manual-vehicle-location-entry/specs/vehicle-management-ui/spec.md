## ADDED Requirements

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
