## Why

The `ser_zone_ticket_required` notification is currently resent on every location poll when a vehicle is stationary in an SER zone during enforcement with no active ticket. This happens because the system re-evaluates the requirement every cycle (intentionally, since time alone can flip the answer) but the notification handler has no memory of having already notified. The result is spam in the user's channel.

## What Changes

- Introduce a first-class `VehicleSerRequirementState` per vehicle that tracks whether a SER ticket is currently required and for which zone.
- Add a new application use case, `EvaluateSerTicketRequirementState`, that processes `VehicleLocationUpdated` events, compares the computed requirement against the stored state, and emits domain events on transitions.
- Add `SerTicketRequirementActivated` and `SerTicketRequirementDeactivated` domain events.
- Change `SerTicketNotificationTriggerHandler` so it subscribes to `SerTicketRequirementActivated` instead of `VehicleLocationUpdated`; notifications are now sent only when the requirement becomes active.
- Keep `SerTicketCreationTriggerHandler` subscribed to `VehicleLocationUpdated` so automatic ticket creation keeps its existing retry behavior.
- Add an audit table, `user_ser_requirement_notifications`, recording which user was notified about which activation event.
- Add PostgreSQL repositories and Alembic migrations for the new tables.

## Capabilities

### New Capabilities
- `ser-ticket-requirement-state`: Tracks the computed SER ticket requirement as vehicle-level state and emits activation/deactivation domain events on transitions.

### Modified Capabilities
- `ser-zone-ticket-notification`: The `ser_zone_ticket_required` notification is now triggered by `SerTicketRequirementActivated` rather than directly by `VehicleLocationUpdated`.

## Impact

- New domain entity, events, repository ports, application use case, event handler, and infrastructure repositories.
- New database tables: `vehicle_ser_requirement_states` and `user_ser_requirement_notifications`.
- New Alembic migration.
- Event wiring in `presentation/api/app.py`.
- Unit and integration tests for the new capability and updated tests for the modified notification handler.
- No API changes; no breaking changes to external behavior other than eliminating repeat notifications.
