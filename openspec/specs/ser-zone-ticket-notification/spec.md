### Requirement: SerTicketNotificationTriggerHandler notifies all vehicle accessors about SER-ticket-related events
When `DetermineSerTicketRequirement` reports a ticket is required for the zone containing a `VehicleLocationUpdated` event's coordinates, `SerTicketNotificationTriggerHandler` SHALL:
1. Look up the `Vehicle` for `event.vehicle_id`. If no such vehicle exists, it SHALL skip silently (no notification, no error).
2. Skip silently, before any other lookup, if the owner's `UserPreferences.auto_create_ticket` is `true`.
3. Resolve the notification recipient list as the vehicle's `owner_id` plus the `user_id` of every active `VehicleShare` for that vehicle.
4. For each recipient, look up that recipient's own `ser_zone_ticket_required` notification preference. If the preference row is missing or `enabled=false`, skip that recipient silently.
5. For each recipient with the preference enabled, call `SerZoneRecheckGate.evaluate(event, movement_floor_meters=<that recipient's effective threshold>)`. If the returned decision's `should_check` is `False`, skip that recipient silently.
6. If `should_check` is `True`, check whether a ticket is currently required via `DetermineSerTicketRequirement.execute(decision.zone, event.vehicle_id)`. If required, look up that recipient's preferences, render the localized "SER ticket required" message (including the vehicle's license plate and the SER zone number, falling back to the default language if `notification_language` is unset), and call `SendNotification.execute` with the resulting `NotificationMessage`.

Each recipient SHALL be evaluated independently; a recipient's own `auto_create_ticket` does not affect other recipients, and each recipient's own threshold is used.

#### Scenario: Owner and sharee both receive ticket-required notification when enabled
- **WHEN** a ticket is required, the owner's `auto_create_ticket` is `false`, and both the owner and a sharee have `ser_zone_ticket_required` enabled
- **THEN** `SendNotification.execute` is called once for the owner and once for the sharee

#### Scenario: Sharee does not receive notification when their preference disabled
- **WHEN** a ticket is required and a sharee has `ser_zone_ticket_required` `enabled=false`
- **THEN** `SendNotification.execute` is not called for that sharee
- **THEN** the owner still receives the notification if their preference is enabled

#### Scenario: Owner's auto_create_ticket suppresses only the owner path
- **WHEN** a `VehicleLocationUpdated` event is published for a vehicle whose owner has `auto_create_ticket=true` but a sharee has it `false` and `ser_zone_ticket_required` enabled
- **THEN** `SendNotification.execute` is not called for the owner
- **THEN** `SendNotification.execute` is called for the sharee if the ticket is still required and the sharee's recheck gate passes

## ADDED Requirements

### Requirement: SerTicketNotificationTriggerHandler notifies all accessors when an automatic ticket is created
When `SerTicketCreated` is published, `SerTicketNotificationTriggerHandler` SHALL resolve the recipient list as the vehicle's `owner_id` plus every active sharee's `user_id`. For each recipient, it SHALL look up that recipient's own `ser_ticket_created` notification preference; if the row is missing or `enabled=false`, it SHALL skip that recipient silently. Otherwise, it SHALL convert both `event.start_date` and `event.end_date` into that recipient's `UserPreferences.timezone` (falling back to UTC when unset or not a recognized IANA zone) via `format_local_datetime`, render the localized message, and call `SendNotification.execute`.

#### Scenario: Owner and sharee both receive ticket-created notification when enabled
- **WHEN** `SerTicketCreated` is published and both the owner and a sharee have `ser_ticket_created` enabled
- **THEN** `SendNotification.execute` is called once for the owner and once for the sharee

#### Scenario: Sharee's disabled preference skips only that sharee
- **WHEN** `SerTicketCreated` is published, the owner has `ser_ticket_created` enabled, and a sharee has it disabled
- **THEN** `SendNotification.execute` is called for the owner
- **THEN** `SendNotification.execute` is not called for the sharee

### Requirement: SerTicketNotificationTriggerHandler notifies all accessors when automatic ticket creation fails
When `SerTicketCreationFailed` is published, `SerTicketNotificationTriggerHandler` SHALL resolve the recipient list as the vehicle's `owner_id` plus every active sharee's `user_id`. For each recipient, it SHALL look up that recipient's own `ser_ticket_creation_failed` notification preference; if the row is missing or `enabled=false`, it SHALL skip that recipient silently. Otherwise, it SHALL render one generic localized message stating the automatic SER ticket for the event's zone number could not be created and must be created manually — the message SHALL NOT include the event's `reason` field or any other technical or exception detail — and call `SendNotification.execute`.

#### Scenario: Owner and sharee both receive failure notification when enabled
- **WHEN** `SerTicketCreationFailed` is published and both the owner and a sharee have `ser_ticket_creation_failed` enabled
- **THEN** `SendNotification.execute` is called once for the owner and once for the sharee

#### Scenario: Sharee's disabled preference skips only that sharee
- **WHEN** `SerTicketCreationFailed` is published, the owner has `ser_ticket_creation_failed` enabled, and a sharee has it disabled
- **THEN** `SendNotification.execute` is called for the owner
- **THEN** `SendNotification.execute` is not called for the sharee
