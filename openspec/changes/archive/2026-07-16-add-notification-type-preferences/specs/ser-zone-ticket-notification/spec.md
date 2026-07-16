## MODIFIED Requirements

### Requirement: SerTicketTriggerHandler notifies the owner when a ticket is required
When `DetermineSerTicketRequirement` reports a ticket is required for the zone containing a `VehicleLocationUpdated` event's coordinates, `SerTicketTriggerHandler` SHALL:
1. Look up the `Vehicle` for `event.vehicle_id`. If no such vehicle exists, it SHALL skip silently (no notification, no error).
2. Look up the vehicle owner's `ser_zone_ticket_required` notification preference. If the preference row is missing or `enabled=false`, it SHALL skip silently — before performing any previous-location or zone lookup.
3. Look up the vehicle's previous recorded location via `VehicleLocationRepository.get_previous`. If not `None`, compute the distance to the event's coordinates; resolve the effective threshold as the user's `ser_zone_ticket_required` preference `config.threshold_m` if set, otherwise `DEFAULT_NOTIFICATION_MOVEMENT_THRESHOLD_METERS`. If the distance is below this threshold, it SHALL skip silently. A vehicle's first-ever recorded location (no previous location) does NOT skip this step — it always proceeds to the zone check.
4. Check zone containment via `FindContainingSerZone` and whether a ticket is currently required via `DetermineSerTicketRequirement`. If required, look up the vehicle owner's preferences, render the localized "SER ticket required" message (including the vehicle's license plate and the SER zone number, falling back to the default language if `notification_language` is unset), and call `SendNotification.execute` with the resulting `NotificationMessage`.

This capability's threshold is independent of `location_moved`'s: a user may configure a different `threshold_m` for `ser_zone_ticket_required` than for `location_moved`.

#### Scenario: Disabled preference skips before any location or zone lookup
- **WHEN** a `VehicleLocationUpdated` event is published for a vehicle whose owner has `ser_zone_ticket_required` `enabled=false`
- **THEN** `SendNotification.execute` is not called
- **THEN** `VehicleLocationRepository.get_previous` and `FindContainingSerZone.execute` are not called

#### Scenario: Ticket required inside a zone triggers a notification
- **WHEN** `DetermineSerTicketRequirement` returns `True` for the zone containing a `VehicleLocationUpdated` event's coordinates, and the owner's `ser_zone_ticket_required` preference is enabled and the movement meets its effective threshold (or there is no previous location)
- **THEN** `SendNotification.execute` is called for the vehicle owner with a message stating a SER ticket must be created, containing the vehicle's plate and the zone number

#### Scenario: Movement below the effective threshold skips the zone check
- **WHEN** a `VehicleLocationUpdated` event's coordinates are less than the owner's effective `ser_zone_ticket_required` threshold away from the vehicle's previous recorded location
- **THEN** `FindContainingSerZone.execute` is not called and `SendNotification.execute` is not called

#### Scenario: No ticket required outside all zones
- **WHEN** `DetermineSerTicketRequirement` returns `False` (the location is outside all SER zones)
- **THEN** `SendNotification.execute` is not called

#### Scenario: A vehicle that no longer exists is skipped without error
- **WHEN** a `VehicleLocationUpdated` event references a `vehicle_id` with no matching `Vehicle`
- **THEN** the handler completes without raising and without calling `SendNotification.execute`

#### Scenario: Message is localized to the owner's notification language
- **WHEN** a ticket-required notification is triggered for an owner whose `notification_language` is `"es"`
- **THEN** the message text is rendered in Spanish

#### Scenario: Message falls back to the default language when unset
- **WHEN** a ticket-required notification is triggered for an owner with no `notification_language` set
- **THEN** the message text is rendered in the default language

#### Scenario: No automatic ticket creation
- **WHEN** a ticket-required notification is sent
- **THEN** no `SerTicketProvider` or ticket-creation code path is invoked — this change only notifies
