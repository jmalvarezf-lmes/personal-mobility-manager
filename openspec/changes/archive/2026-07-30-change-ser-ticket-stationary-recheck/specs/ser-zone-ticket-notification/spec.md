## MODIFIED Requirements

### Requirement: SerTicketNotificationTriggerHandler notifies the owner when a ticket is required
When `DetermineSerTicketRequirement` reports a ticket is required for the zone containing a `VehicleLocationUpdated` event's coordinates, `SerTicketNotificationTriggerHandler` (renamed from `SerTicketTriggerHandler`) SHALL:
1. Look up the `Vehicle` for `event.vehicle_id`. If no such vehicle exists, it SHALL skip silently (no notification, no error).
2. Skip silently, before any other lookup, if the owner's `UserPreferences.auto_create_ticket` is `true` — when auto-creation is enabled, `SerTicketCreationTriggerHandler` (see `ser-ticket-auto-creation`) owns this event instead, and no "ticket required" obligation notice is sent.
3. Look up the vehicle owner's `ser_zone_ticket_required` notification preference. If the preference row is missing or `enabled=false`, it SHALL skip silently — before calling `SerZoneRecheckGate.evaluate`.
4. Call `SerZoneRecheckGate.evaluate(event, movement_floor_meters=<the owner's effective threshold>)` (see the `ser-zone-recheck-gate` capability), where the effective threshold is the user's `ser_zone_ticket_required` preference `config.threshold_m` if set, otherwise `DEFAULT_NOTIFICATION_MOVEMENT_THRESHOLD_METERS` — independent of `SerTicketCreationTriggerHandler`'s own floor, never sharing a call or value. If the returned decision's `should_check` is `False`, it SHALL skip silently.
5. If `should_check` is `True`, check whether a ticket is currently required via `DetermineSerTicketRequirement.execute(decision.zone, event.vehicle_id)` — passing the vehicle id so a matching parking exemption (see `vehicle-ser-parking-exemption`) suppresses the requirement. If required, look up the vehicle owner's preferences, render the localized "SER ticket required" message (including the vehicle's license plate and the SER zone number, falling back to the default language if `notification_language` is unset), and call `SendNotification.execute` with the resulting `NotificationMessage`.

This capability's threshold is independent of `location_moved`'s: a user may configure a different `threshold_m` for `ser_zone_ticket_required` than for `location_moved`. `ser_zone_ticket_required`'s stored `config` continues to exist and is reused by `SerTicketCreationTriggerHandler`'s own movement gate even while its `enabled` flag is locked off (see `ser-ticket-auto-creation`).

#### Scenario: Skips entirely when automatic ticket creation is enabled
- **WHEN** a `VehicleLocationUpdated` event is published for a vehicle whose owner has `auto_create_ticket=true`
- **THEN** `SendNotification.execute` is not called
- **THEN** the owner's `ser_zone_ticket_required` preference is not consulted, and `SerZoneRecheckGate.evaluate` is not called

#### Scenario: Disabled preference skips before calling the recheck gate
- **WHEN** a `VehicleLocationUpdated` event is published for a vehicle whose owner has `auto_create_ticket=false` and `ser_zone_ticket_required` `enabled=false`
- **THEN** `SendNotification.execute` is not called
- **THEN** `SerZoneRecheckGate.evaluate` is not called

#### Scenario: Ticket required inside a zone triggers a notification
- **WHEN** `DetermineSerTicketRequirement.execute(zone, event.vehicle_id)` returns `True` for the zone containing a `VehicleLocationUpdated` event's coordinates, the owner's `auto_create_ticket` is `false`, the owner's `ser_zone_ticket_required` preference is enabled, and `SerZoneRecheckGate.evaluate` returns `should_check=True`
- **THEN** `SendNotification.execute` is called for the vehicle owner with a message stating a SER ticket must be created, containing the vehicle's plate and the zone number

#### Scenario: SerZoneRecheckGate signals no check needed
- **WHEN** `SerZoneRecheckGate.evaluate` returns `should_check=False` for a `VehicleLocationUpdated` event
- **THEN** `DetermineSerTicketRequirement.execute` is not called and `SendNotification.execute` is not called

#### Scenario: A stationary vehicle with no active ticket still gets rechecked
- **WHEN** a `VehicleLocationUpdated` event's coordinates are unchanged from the vehicle's previous recorded location, and the vehicle currently holds no active `ParkingTicket`
- **THEN** `SerZoneRecheckGate.evaluate` returns `should_check=True`
- **THEN** `DetermineSerTicketRequirement.execute` is called with the resolved zone

#### Scenario: No ticket required outside all zones
- **WHEN** `DetermineSerTicketRequirement.execute(zone, event.vehicle_id)` returns `False` (the location is outside all SER zones)
- **THEN** `SendNotification.execute` is not called

#### Scenario: A matching vehicle exemption suppresses the notification
- **WHEN** `DetermineSerTicketRequirement.execute(zone, event.vehicle_id)` returns `False` because the vehicle has a stored exemption matching the containing zone's `(city_code, zone_number)`
- **THEN** `SendNotification.execute` is not called, the same as any other "no ticket required" outcome

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
- **WHEN** a ticket-required notification is sent by `SerTicketNotificationTriggerHandler`
- **THEN** no `SerTicketProvider` or ticket-creation code path is invoked — this handler only ever notifies, never creates
