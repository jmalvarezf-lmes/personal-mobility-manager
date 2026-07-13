## ADDED Requirements

### Requirement: SerTicketTriggerHandler notifies the owner when a ticket is required
When `DetermineSerTicketRequirement` reports a ticket is required for the zone containing a `VehicleLocationUpdated` event's coordinates, `SerTicketTriggerHandler` SHALL:
1. Look up the `Vehicle` for `event.vehicle_id`. If no such vehicle exists, it SHALL skip silently (no notification, no error).
2. Look up the vehicle owner's preferences, render the localized "SER ticket required" message (including the vehicle's license plate and the SER zone number, falling back to the default language if `notification_language` is unset), and call `SendNotification.execute` with the resulting `NotificationMessage`.

This capability does not implement per-event-type opt-in/opt-out, matching the existing movement-notification behavior — any user with a `preferred_notification_channel` connected receives this notification kind unconditionally whenever a ticket is required.

#### Scenario: Ticket required inside a zone triggers a notification
- **WHEN** `DetermineSerTicketRequirement` returns `True` for the zone containing a `VehicleLocationUpdated` event's coordinates
- **THEN** `SendNotification.execute` is called for the vehicle owner with a message stating a SER ticket must be created, containing the vehicle's plate and the zone number

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
