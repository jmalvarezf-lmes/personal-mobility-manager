## MODIFIED Requirements

### Requirement: SerTicketNotificationTriggerHandler notifies all vehicle accessors when a SER ticket requirement becomes active
When `SerTicketRequirementActivated` is published, `SerTicketNotificationTriggerHandler` SHALL:
1. Look up the `Vehicle` for `event.vehicle_id`. If no such vehicle exists, it SHALL skip silently (no notification, no error).
2. Skip silently, before any other lookup, if the owner's `UserPreferences.auto_create_ticket` is `true`.
3. Resolve the notification recipient list as the vehicle's `owner_id` plus the `user_id` of every active `VehicleShare` for that vehicle.
4. For each recipient, look up that recipient's own `ser_zone_ticket_required` notification preference. If the preference row is missing or `enabled=false`, skip that recipient silently.
5. Look up that recipient's preferences, render the localized "SER ticket required" message (including the vehicle's license plate and the SER zone number from the event, falling back to the default language if `notification_language` is unset), and call `SendNotification.execute` with the resulting `NotificationMessage`.

Each recipient SHALL be evaluated independently; a recipient's own `auto_create_ticket` does not affect other recipients.

#### Scenario: Owner and sharee both receive ticket-required notification when enabled
- **WHEN** a `SerTicketRequirementActivated` event is published, the owner's `auto_create_ticket` is `false`, and both the owner and a sharee have `ser_zone_ticket_required` enabled
- **THEN** `SendNotification.execute` is called once for the owner and once for the sharee

#### Scenario: Sharee does not receive notification when their preference disabled
- **WHEN** a `SerTicketRequirementActivated` event is published and a sharee has `ser_zone_ticket_required` `enabled=false`
- **THEN** `SendNotification.execute` is not called for that sharee
- **THEN** the owner still receives the notification if their preference is enabled

#### Scenario: Owner's auto_create_ticket suppresses only the owner path
- **WHEN** a `SerTicketRequirementActivated` event is published for a vehicle whose owner has `auto_create_ticket=true` but a sharee has it `false` and `ser_zone_ticket_required` enabled
- **THEN** `SendNotification.execute` is not called for the owner
- **THEN** `SendNotification.execute` is called for the sharee

#### Scenario: Stationary vehicle does not trigger repeat notifications
- **WHEN** a vehicle remains parked in the same SER zone during active enforcement and multiple `VehicleLocationUpdated` events are published
- **THEN** only the first event that causes a transition to `is_required=true` results in a `SerTicketRequirementActivated` event
- **THEN** subsequent events without a transition do not result in any `ser_zone_ticket_required` notification
