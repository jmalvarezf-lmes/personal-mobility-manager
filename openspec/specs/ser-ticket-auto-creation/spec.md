### Requirement: SerTicketCreationTriggerHandler creates a SER ticket when required and auto-creation is enabled
When a `VehicleLocationUpdated` event is published, `SerTicketCreationTriggerHandler` SHALL:
1. Look up the `Vehicle` for `event.vehicle_id`. If no such vehicle exists, it SHALL skip silently (no ticket creation, no error).
2. Skip silently if the owner's `UserPreferences.auto_create_ticket` is not `true` — this handler only ever acts when it is.
3. Call `SerZoneRecheckGate.evaluate(event, movement_floor_meters=get_ser_ticket_creation_zone_change_floor_meters())` (see the `ser-zone-recheck-gate` capability). If the returned decision's `should_check` is `False`, it SHALL skip silently without calling `DetermineSerTicketRequirement`. The gate's `movement_floor_meters` for this handler remains the fixed technical floor resolved by `get_ser_ticket_creation_zone_change_floor_meters()` (default 10 meters, not a user preference) — unchanged in value from before this handler delegated to the gate.
4. If `should_check` is `True`, check whether a ticket is currently required for the decision's resolved `zone` via `DetermineSerTicketRequirement.execute(zone, event.vehicle_id)` — unchanged from `ser-zone-ticket-notification`, including exemption handling and the active-ticket idempotency short-circuit, which is scoped to the zone being checked (see the `ser-ticket-requirement` capability): an active ticket for the *same* zone still suppresses creation, but an active ticket for a *different* zone no longer does. If not required, skip silently.
5. If required, resolve the provider as the first entry of `UserSerProviderConfigRepository.list_connected_providers(owner.user_id)` and call `CreateSerTicket.execute(user_id=owner.user_id, vehicle_id=event.vehicle_id, provider=<resolved provider>, duration_minutes=owner's default_ticket_duration_minutes, location=GeoLocation(lat=event.latitude, lng=event.longitude), auto_created=True)` — the event's own coordinates, not a fresh location lookup.
6. On success, publish `SerTicketCreated` carrying the vehicle id, user id, the zone's number, the created ticket's `created_at` as `start_date`, and the created ticket's `end_date`.
7. On any exception raised by `CreateSerTicket.execute`, publish `SerTicketCreationFailed` carrying the vehicle id, user id, the zone's number, and a closed-vocabulary `reason` derived from the exception type — never the raw exception message or `str(exc)`.

The entire handler body SHALL be wrapped in a broad try/except so a failure here never breaks the caller or blocks `SerTicketNotificationTriggerHandler` from running for the same event, matching the sibling handler's existing convention.

#### Scenario: Ticket created when required and the vehicle changed SER zone
- **WHEN** `DetermineSerTicketRequirement` returns `True` for the zone containing a `VehicleLocationUpdated` event's coordinates, the owner's `auto_create_ticket` is `true`, and that zone differs from the zone containing the vehicle's previous recorded location (or there is no previous location)
- **THEN** `CreateSerTicket.execute` is called with the resolved provider, the owner's `default_ticket_duration_minutes`, the event's coordinates as `location`, and `auto_created=True`
- **THEN** `SerTicketCreated` is published on success

#### Scenario: No creation when auto_create_ticket is disabled
- **WHEN** a `VehicleLocationUpdated` event is published for a vehicle whose owner has `auto_create_ticket=false`
- **THEN** `CreateSerTicket.execute` is not called
- **THEN** neither `SerTicketCreated` nor `SerTicketCreationFailed` is published

#### Scenario: SerZoneRecheckGate signals no check needed
- **WHEN** `SerZoneRecheckGate.evaluate` returns `should_check=False` for a `VehicleLocationUpdated` event
- **THEN** `DetermineSerTicketRequirement.execute` is not called and `CreateSerTicket.execute` is not called

#### Scenario: A stationary vehicle with no active ticket still gets rechecked
- **WHEN** a `VehicleLocationUpdated` event's coordinates are unchanged from the vehicle's previous recorded location, and the vehicle currently holds no active `ParkingTicket`
- **THEN** `SerZoneRecheckGate.evaluate` returns `should_check=True`
- **THEN** `DetermineSerTicketRequirement.execute` is called with the resolved zone

#### Scenario: Transitioning out of all SER zones skips creation
- **WHEN** the vehicle's previous recorded location was inside a SER zone and the event's coordinates are inside no SER zone (a zone transition, since the two states differ)
- **THEN** `DetermineSerTicketRequirement.execute` is called with `zone=None`, returns `False` via its existing zone-is-None short-circuit, and `CreateSerTicket.execute` is not called

#### Scenario: No ticket required outside all zones
- **WHEN** `DetermineSerTicketRequirement.execute(zone, event.vehicle_id)` returns `False` (the location is outside all SER zones, or enforcement is not currently active)
- **THEN** `CreateSerTicket.execute` is not called

#### Scenario: Zone changed away from an existing ticket's zone still creates a new ticket
- **WHEN** the vehicle has an active `ParkingTicket` whose `(city_code, zone_number)` is for zone A, and the event's coordinates are in a different zone B that requires a ticket (enforcement active, no exemption)
- **THEN** `DetermineSerTicketRequirement.execute` does not short-circuit on the existing active ticket for zone A, and `CreateSerTicket.execute` is called for zone B

#### Scenario: A matching vehicle exemption suppresses ticket creation
- **WHEN** `DetermineSerTicketRequirement.execute(zone, event.vehicle_id)` returns `False` because the vehicle has a stored exemption matching the containing zone's `(city_code, zone_number)`
- **THEN** `CreateSerTicket.execute` is not called, the same as any other "no ticket required" outcome

#### Scenario: A vehicle that no longer exists is skipped without error
- **WHEN** a `VehicleLocationUpdated` event references a `vehicle_id` with no matching `Vehicle`
- **THEN** the handler completes without raising and without calling `CreateSerTicket.execute`

#### Scenario: Provider failure is translated into SerTicketCreationFailed without the raw exception
- **WHEN** `CreateSerTicket.execute` raises any exception (e.g. `SerProviderSessionNotFoundError`, `SerZoneNotFoundError`, `SerProviderVehicleNotFoundError`, `SerProviderApiError`)
- **THEN** `SerTicketCreationFailed` is published with a closed-vocabulary `reason`
- **THEN** the raw exception message is not included on the published event

#### Scenario: Auto-created ticket is persisted with auto_created=True
- **WHEN** `CreateSerTicket.execute` succeeds as a result of this handler's call
- **THEN** the persisted `ParkingTicket` has `auto_created=True` and `latitude`/`longitude` matching the triggering event's coordinates

---

### Requirement: SerTicketCreated and SerTicketCreationFailed are domain events published only by the auto-creation trigger
The system SHALL define `SerTicketCreated` (fields: `vehicle_id`, `user_id`, `zone_number`, `start_date`, `end_date`) and `SerTicketCreationFailed` (fields: `vehicle_id`, `user_id`, `zone_number`, `reason`) as frozen dataclass domain events. `SerTicketCreated.start_date` SHALL be the created `ParkingTicket`'s `created_at` value — the moment the provider confirmed the ticket's creation, treated as the start of its validity window. Both events SHALL be published exclusively by `SerTicketCreationTriggerHandler`. `CreateSerTicket` itself SHALL NOT publish either event, so the manual `POST /parking/ser-tickets` flow is unaffected by this change.

#### Scenario: Manual ticket creation does not publish either event
- **WHEN** a ticket is created via `POST /parking/ser-tickets` (not triggered by `VehicleLocationUpdated`)
- **THEN** neither `SerTicketCreated` nor `SerTicketCreationFailed` is published

---

### Requirement: SerTicketNotificationTriggerHandler notifies the owner when an automatic ticket is created
When `SerTicketCreated` is published, `SerTicketNotificationTriggerHandler` SHALL look up the owner's `ser_ticket_created` notification preference; if the row is missing or `enabled=false`, it SHALL skip silently. Otherwise, it SHALL convert both `event.start_date` and `event.end_date` into the owner's `UserPreferences.timezone` (falling back to UTC when unset or not a recognized IANA zone) via `format_local_datetime`, render the localized message stating a SER ticket for the event's zone number is valid from the formatted `start_date` to the formatted `end_date`, and call `SendNotification.execute`.

#### Scenario: Enabled preference triggers the created notification with both dates
- **WHEN** `SerTicketCreated` is published and the owner's `ser_ticket_created` preference is enabled
- **THEN** `SendNotification.execute` is called with a message stating a SER ticket for the zone is valid from the ticket's (localized) `start_date` to its (localized) `end_date`

#### Scenario: Disabled preference skips the notification
- **WHEN** `SerTicketCreated` is published and the owner's `ser_ticket_created` preference is missing or disabled
- **THEN** `SendNotification.execute` is not called

#### Scenario: Message is localized to the owner's notification language
- **WHEN** a ticket-created notification is triggered for an owner whose `notification_language` is `"es"`
- **THEN** the message text is rendered in Spanish

#### Scenario: Dates are formatted in the owner's configured timezone
- **WHEN** a ticket-created notification is triggered for an owner whose `timezone` is `"Europe/Madrid"` and `event.start_date`/`event.end_date` are UTC datetimes
- **THEN** both dates in the rendered message reflect `Europe/Madrid` local time, not UTC

#### Scenario: Dates fall back to UTC when no timezone is set
- **WHEN** a ticket-created notification is triggered for an owner with no `timezone` set
- **THEN** both dates in the rendered message are formatted in UTC

---

### Requirement: SerTicketNotificationTriggerHandler notifies the owner when automatic ticket creation fails
When `SerTicketCreationFailed` is published, `SerTicketNotificationTriggerHandler` SHALL look up the owner's `ser_ticket_creation_failed` notification preference; if the row is missing or `enabled=false`, it SHALL skip silently. Otherwise, it SHALL render one generic localized message stating the automatic SER ticket for the event's zone number could not be created and must be created manually — the message SHALL NOT include the event's `reason` field or any other technical or exception detail — and call `SendNotification.execute`.

#### Scenario: Enabled preference triggers the failure notification
- **WHEN** `SerTicketCreationFailed` is published and the owner's `ser_ticket_creation_failed` preference is enabled
- **THEN** `SendNotification.execute` is called with a generic message that does not contain the event's `reason` value or any exception text

#### Scenario: Disabled preference skips the notification
- **WHEN** `SerTicketCreationFailed` is published and the owner's `ser_ticket_creation_failed` preference is missing or disabled
- **THEN** `SendNotification.execute` is not called

## ADDED Requirements

### Requirement: Automatic SER ticket creation is scoped to the vehicle owner
When `SerTicketCreationTriggerHandler` creates an automatic SER ticket, it SHALL use the vehicle owner's `user_id` and the owner's connected SER provider configuration, regardless of any sharees. Sharees SHALL NOT trigger, authorize, or fund automatic ticket creation.

#### Scenario: Auto-creation uses owner user_id
- **WHEN** `SerTicketCreationTriggerHandler` calls `CreateSerTicket.execute`
- **THEN** the `user_id` argument is the vehicle's `owner_id`

#### Scenario: Sharee presence does not alter auto-creation behavior
- **WHEN** a vehicle has active sharees and a location event triggers auto-creation
- **THEN** the ticket is created using the owner's provider session and preferences
- **THEN** no sharee provider session is consulted
