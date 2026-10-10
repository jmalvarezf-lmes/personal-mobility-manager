## Purpose

Track whether a SER ticket is currently required for a vehicle as a durable state, and emit domain events when that requirement becomes active or inactive, so that notifications and other side effects can react to transitions instead of every location poll.

## ADDED Requirements

### Requirement: VehicleSerRequirementState represents the current requirement for a vehicle
The system SHALL define a `VehicleSerRequirementState` domain entity with the following fields: `vehicle_id` (UUID), `city_code` (text or null), `zone_number` (text or null), `is_required` (boolean), `activated_at` (datetime or null), and `last_evaluated_at` (datetime).

`city_code` and `zone_number` SHALL identify the SER zone for which the requirement is currently active; when `is_required` is `false`, both MAY be null.

#### Scenario: State is initialized for a vehicle on first evaluation
- **WHEN** `EvaluateSerTicketRequirementState` runs for a vehicle that has no stored state
- **THEN** a default state with `is_required=false` is used as the baseline before comparing against the current computed requirement

---

### Requirement: EvaluateSerTicketRequirementState emits transition events
The system SHALL provide an `EvaluateSerTicketRequirementState` application use case that accepts a `VehicleLocationUpdated` event and the vehicle's current `VehicleSerRequirementState`, computes whether a SER ticket is required, and updates the stored state.

When the stored state has `is_required=false` and the computed requirement is `true`, the use case SHALL publish a `SerTicketRequirementActivated` event and update the stored state to `is_required=true` with the current zone and activation timestamp.

When the stored state has `is_required=true` and the computed requirement is `false`, the use case SHALL publish a `SerTicketRequirementDeactivated` event with a deactivation reason and update the stored state to `is_required=false`.

When the computed requirement matches the stored state, the use case SHALL update `last_evaluated_at` and SHALL NOT publish either event.

#### Scenario: Requirement becomes active
- **WHEN** the stored state is `is_required=false` and the computed requirement is `true` for zone `163` in `madrid`
- **THEN** the stored state is updated to `is_required=true` with `city_code=madrid` and `zone_number=163`
- **THEN** a `SerTicketRequirementActivated` event is published carrying the vehicle id, the zone, and the activation timestamp

#### Scenario: Requirement becomes inactive
- **WHEN** the stored state is `is_required=true` for zone `163` in `madrid` and the computed requirement is `false` because the vehicle left the zone
- **THEN** the stored state is updated to `is_required=false`
- **THEN** a `SerTicketRequirementDeactivated` event is published with reason `left_zone`

#### Scenario: Requirement stays active
- **WHEN** the stored state is `is_required=true` for zone `163` in `madrid` and the computed requirement remains `true`
- **THEN** only `last_evaluated_at` is updated
- **THEN** no transition event is published

---

### Requirement: Active state is re-evaluated reliably to detect deactivation
When the stored `VehicleSerRequirementState.is_required` is `true`, the use case SHALL call `DetermineSerTicketRequirement.execute` on every matching `VehicleLocationUpdated` event to detect deactivation.

When the stored `VehicleSerRequirementState.is_required` is `false`, the use case MAY use `SerZoneRecheckGate.evaluate` to avoid unnecessary zone lookups, while still evaluating when the gate signals that a recheck is warranted.

#### Scenario: Active state detects ticket creation
- **WHEN** the stored state is `is_required=true` and `DetermineSerTicketRequirement.execute` returns `false` because an active parking ticket now covers the zone
- **THEN** a `SerTicketRequirementDeactivated` event is published with reason `ticket_active`

#### Scenario: Inactive state uses gate optimization
- **WHEN** the stored state is `is_required=false`, the vehicle holds an active parking ticket, and the gate signals `should_check=false`
- **THEN** no zone lookup or requirement computation is performed
- **THEN** `last_evaluated_at` is updated

---

### Requirement: Deactivation reasons are a single source of truth
The system SHALL define a closed enumeration of deactivation reasons: `left_zone`, `enforcement_inactive`, `ticket_active`, and `exempt`. The enumeration SHALL be defined in exactly one place in the domain layer and SHALL be the only valid values for `SerTicketRequirementDeactivated.reason`.

#### Scenario: Deactivation event uses a valid reason
- **WHEN** a `SerTicketRequirementDeactivated` event is constructed
- **THEN** its `reason` field is one of the defined enumeration values

---

### Requirement: Notification audit records are persisted per activation
The system SHALL provide a `UserSerRequirementNotificationRepository` port and a PostgreSQL implementation backed by a `user_ser_requirement_notifications` table. When `SerTicketNotificationTriggerHandler` sends a `ser_zone_ticket_required` notification in response to a `SerTicketRequirementActivated` event, it SHALL record a row containing the recipient's `user_id`, the `vehicle_id`, the zone's `city_code` and `zone_number`, the event's `latitude` and `longitude`, the event's `activated_at` timestamp, and the current notification timestamp.

#### Scenario: Notification is audited
- **WHEN** a `ser_zone_ticket_required` notification is sent to a user for a `SerTicketRequirementActivated` event
- **THEN** a row is inserted into `user_ser_requirement_notifications` with the recipient, vehicle, zone, coordinates, and both timestamps

#### Scenario: Audit does not block notification on failure
- **WHEN** the audit repository write fails after a notification is sent
- **THEN** the notification is still considered delivered and the failure is logged; no retry of the notification occurs because of the audit failure
