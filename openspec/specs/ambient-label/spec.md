### Requirement: AmbientLabel value object constrains valid labels
The system SHALL define `AmbientLabel` as a closed enum with exactly five values: `A`, `B`, `C`, `ECO`, `ZERO` (serialized as `"0"`). No other value SHALL be persisted as a resolved label.

#### Scenario: Valid label persisted
- **WHEN** a lookup resolves to one of A, B, C, ECO, or 0
- **THEN** the corresponding `AmbientLabel` value is stored

### Requirement: Vehicle ambient label is looked up and stored per vehicle
The system SHALL persist, for each vehicle, at most one ambient label lookup record keyed by `vehicle_id`, containing a nullable `label` (`AmbientLabel`), a `status` (`found` | `not_found` | `error`), and a nullable `last_checked_at` timestamp.

#### Scenario: No lookup attempted yet
- **WHEN** a vehicle has never had a lookup attempted
- **THEN** no `vehicle_ambient_labels` row exists for it, and read endpoints report the label as absent

#### Scenario: Lookup resolves a label
- **WHEN** a lookup for a vehicle's plate returns a confident label
- **THEN** the row's `label` is set to that value, `status` is set to `found`, and `last_checked_at` is set to the current time

#### Scenario: Lookup finds no record
- **WHEN** DGT's response indicates no result was found for the plate
- **THEN** the row's `status` is set to `not_found`, `label` remains null, and `last_checked_at` is set to the current time

#### Scenario: Lookup fails or cannot be parsed
- **WHEN** the HTTP request errors, times out, or the response matches none of the known result shapes
- **THEN** the row's `status` is set to `error`, `label` remains null, and `last_checked_at` is set to the current time

### Requirement: DGT response parsing distinguishes found, no-label, and not-found by container class
The parser SHALL branch on the response's result container class before extracting a label: a `border-success` container SHALL be parsed for a label; an `alert-warning` container SHALL be treated as a confirmed `A` (no label) result; an `alert-danger` container, or a response matching none of these three shapes, SHALL be treated as inconclusive.

#### Scenario: Success container yields a label
- **WHEN** the response contains a `border-success` result container referencing `distintivo_B_sin_fondo.svg` and the text "Distintivo Ambiental B"
- **THEN** the parser resolves `AmbientLabel.B` with `status = found`

#### Scenario: Warning container yields confirmed no-label
- **WHEN** the response contains an `alert-warning` container with the text "Sin distintivo. Tu vehículo no cumple los requisitos..."
- **THEN** the parser resolves `AmbientLabel.A` with `status = found`

#### Scenario: Danger container yields inconclusive result
- **WHEN** the response contains an `alert-danger` container with the text "No se ha encontrado ningún resultado..."
- **THEN** the parser resolves `status = not_found` with no label

#### Scenario: Cross-check mismatch is treated as an error, not trusted
- **WHEN** a `border-success` container's image filename and prose text imply different labels
- **THEN** the parser resolves `status = error` with no label, rather than persisting either conflicting value

### Requirement: Vehicle registration best-effort triggers a lookup
When a vehicle is registered with a non-null `license_plate`, the system SHALL attempt an ambient label lookup synchronously as part of registration, but SHALL NOT allow a lookup failure, timeout, or unexpected exception to cause the registration request to fail.

#### Scenario: Lookup succeeds during registration
- **WHEN** a vehicle is registered with a license plate and the DGT lookup succeeds
- **THEN** the vehicle is created and its ambient label row reflects the resolved result before the registration response is returned
- **THEN** the registration response itself includes the resolved label (not just the persisted row) — a client SHALL NOT need a follow-up read to see a label that was already resolved synchronously

#### Scenario: Lookup fails during registration
- **WHEN** a vehicle is registered with a license plate and the DGT lookup raises an exception or times out
- **THEN** the vehicle is still created successfully, the registration response is unaffected, and no ambient label row is required to exist yet

#### Scenario: Registration without a plate skips the lookup
- **WHEN** a vehicle is registered with no `license_plate`
- **THEN** no lookup is attempted

### Requirement: Scheduler drains the backlog of vehicles missing a confident label
The system SHALL run a background scheduler that, on each tick, queries vehicles with a non-null `license_plate` and either no ambient label row, or a row with `status != found` whose `last_checked_at` is older than a configured cooldown. For each such vehicle it SHALL perform a lookup, waiting a configured delay (default 5 seconds) between consecutive lookups within the same tick. A failure looking up one vehicle SHALL NOT prevent remaining vehicles in the same tick from being attempted.

#### Scenario: Vehicle missing a label is picked up
- **WHEN** a vehicle has a license plate and no ambient label row
- **THEN** the next scheduler tick attempts a lookup for it

#### Scenario: Found labels are never re-checked
- **WHEN** a vehicle's ambient label row has `status = found`
- **THEN** no scheduler tick attempts a lookup for it again

#### Scenario: Inconclusive results are retried after cooldown, not every tick
- **WHEN** a vehicle's ambient label row has `status = not_found` or `status = error` with `last_checked_at` within the configured cooldown
- **THEN** the scheduler does not attempt a lookup for it until the cooldown has elapsed

#### Scenario: One vehicle's failure does not stop the batch
- **WHEN** a lookup for one vehicle in a tick raises an unexpected exception
- **THEN** the scheduler logs the failure and continues to the next vehicle in the same tick

#### Scenario: Requests within a tick are throttled
- **WHEN** a tick processes more than one vehicle
- **THEN** the scheduler waits at least the configured delay between each consecutive DGT request

### Requirement: Ambient label icon is downloaded and cached once per label value
The system SHALL cache the DGT-provided sticker icon image for each of B, C, ECO, and 0 exactly once, keyed by label value, and SHALL reuse the cached image for every vehicle that resolves to that label rather than re-downloading it. Label A SHALL never have a cached icon, since DGT's confirmed-no-label response contains no image.

#### Scenario: First vehicle resolving a label caches its icon
- **WHEN** a lookup resolves label B for a vehicle and no icon is cached yet for B
- **THEN** the system downloads the icon referenced in the response and stores it keyed by `B`

#### Scenario: Subsequent vehicles reuse the cached icon
- **WHEN** a lookup resolves label B for a vehicle and an icon is already cached for `B`
- **THEN** no icon download is attempted

#### Scenario: Label A never triggers an icon download
- **WHEN** a lookup resolves label A for a vehicle
- **THEN** no icon download is attempted and no cache entry is created for `A`

### Requirement: Ambient label icon is served via a dedicated endpoint
The system SHALL expose `GET /ambient-labels/{label}/icon` returning the cached image bytes and correct content type for `B`, `C`, `ECO`, and `0`. Requesting the icon for label `A`, or for a label with no cache entry yet, SHALL return HTTP 404.

#### Scenario: Cached icon is served
- **WHEN** a client requests `GET /ambient-labels/B/icon` and an icon is cached for `B`
- **THEN** the system responds 200 with the image bytes and correct content type

#### Scenario: Label A has no icon to serve
- **WHEN** a client requests `GET /ambient-labels/A/icon`
- **THEN** the system responds HTTP 404

#### Scenario: Not-yet-cached label returns 404
- **WHEN** a client requests the icon for a label no vehicle has resolved to yet
- **THEN** the system responds HTTP 404

### Requirement: Frontend displays the ambient label icon alongside vehicle info
The vehicle list and vehicle detail views SHALL display the ambient label icon (loaded from the backend endpoint) next to a vehicle's info when its resolved label is `B`, `C`, `ECO`, or `0`. When the resolved label is `A`, the UI SHALL show a "no label" indication without requesting an icon. When the label is unresolved, neither an icon nor a "no label" indication SHALL be shown.

#### Scenario: Vehicle with a stickered label shows its icon
- **WHEN** a vehicle's ambient label is resolved to `B`
- **THEN** the vehicle list and detail views display the `B` icon fetched from `GET /ambient-labels/B/icon`

#### Scenario: Vehicle with label A shows a no-label indication, not an icon
- **WHEN** a vehicle's ambient label is resolved to `A`
- **THEN** the UI shows a "no label" indicator and does not request an icon

#### Scenario: Vehicle with unresolved label shows neither
- **WHEN** a vehicle has no resolved ambient label
- **THEN** the UI shows neither an icon nor a "no label" indicator

### Requirement: Ambient label is exposed on vehicle read endpoints and the registration response
`GET /vehicles`, `GET /vehicles/{id}`, and `POST /vehicles` SHALL include the vehicle's ambient label status: the resolved `label` value when `status = found`, and an indication that no confident label is available otherwise. All three read the same persisted row through the same resolution logic — `POST /vehicles` is not a separate/leaner contract for this field, even though it is for other fields (e.g. `location`).

#### Scenario: Resolved label appears in list and detail responses
- **WHEN** a vehicle's ambient label row has `status = found` and `label = "B"`
- **THEN** `GET /vehicles`, `GET /vehicles/{id}`, and `POST /vehicles` (if resolved by the time the response is built) all include `"B"` for that vehicle

#### Scenario: Unresolved label appears as absent
- **WHEN** a vehicle has no ambient label row, or a row with `status != found`
- **THEN** all three endpoints report the label as null/absent for that vehicle
