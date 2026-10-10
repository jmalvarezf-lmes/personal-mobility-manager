## MODIFIED Requirements

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

### Requirement: Edit Vehicle opens a pre-filled edit form
Clicking Edit on a vehicle card SHALL open an edit modal pre-filled with the current vehicle's editable fields. Edit SHALL only be available to owners.

#### Scenario: Owner opens edit modal
- **WHEN** the owner clicks Edit
- **THEN** the edit modal opens

#### Scenario: Sharee cannot edit
- **WHEN** a sharee views a vehicle card
- **THEN** no Edit button is present
