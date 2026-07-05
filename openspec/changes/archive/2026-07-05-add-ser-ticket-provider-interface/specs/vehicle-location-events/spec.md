## ADDED Requirements

### Requirement: VehicleLocationUpdated domain event
The system SHALL define a `VehicleLocationUpdated` domain event with fields: `vehicle_id` (UUID), `latitude` (float), `longitude` (float), `recorded_at` (datetime), `source` (`"pull"` or `"push"`).

#### Scenario: Event carries the recorded location data
- **WHEN** a `VehicleLocationUpdated` event is constructed
- **THEN** it carries the same `vehicle_id`, coordinates, `recorded_at`, and `source` as the location that was just persisted

---

### Requirement: EventPublisher port for publishing domain events
The system SHALL define an `EventPublisher` abstract interface with `publish(event: DomainEvent) -> None`. Concrete adapters SHALL NOT be assumed to be synchronous or asynchronous by the port signature alone.

#### Scenario: Publishing does not require a specific transport
- **WHEN** a concrete `EventPublisher` implementation is swapped for another (e.g. in-memory for a message-broker-backed one)
- **THEN** no caller of `publish` needs to change, since the port signature is transport-agnostic

---

### Requirement: InMemoryEventPublisher dispatches synchronously in-process
The system SHALL provide an `InMemoryEventPublisher` implementing `EventPublisher`, with a `subscribe(event_type: type, handler: Callable) -> None` method to register handlers. Calling `publish(event)` SHALL synchronously invoke every handler subscribed to `type(event)`, in the same process and thread as the caller.

#### Scenario: Subscribed handler is invoked on publish
- **WHEN** a handler is subscribed to `VehicleLocationUpdated` and a matching event is published
- **THEN** the handler's callable is invoked with that event before `publish` returns

#### Scenario: Publishing an event with no subscribers is a no-op
- **WHEN** an event type with no subscribed handlers is published
- **THEN** `publish` returns without error and without invoking anything

---

### Requirement: RecordVehicleLocation publishes VehicleLocationUpdated after saving
The system SHALL have `RecordVehicleLocation.execute` publish a `VehicleLocationUpdated` event via the injected `EventPublisher`, immediately after successfully persisting the location, for both `source="pull"` and `source="push"` calls.

#### Scenario: Event published after successful pull ingestion
- **WHEN** the scheduler successfully records a pulled location
- **THEN** a `VehicleLocationUpdated` event with `source="pull"` is published after the location is saved

#### Scenario: Event published after successful push ingestion
- **WHEN** the push endpoint successfully records a pushed location
- **THEN** a `VehicleLocationUpdated` event with `source="push"` is published after the location is saved

#### Scenario: No event published on validation failure
- **WHEN** `RecordVehicleLocation.execute` raises `ValueError` due to invalid coordinates or timestamp
- **THEN** no event is published, since the location was never persisted

---

### Requirement: SerTicketTriggerHandler is registered but inert
The system SHALL register a `SerTicketTriggerHandler` as a subscriber to `VehicleLocationUpdated` at application startup. Its handling logic SHALL be a no-op in this change — it SHALL NOT read user preferences, SHALL NOT query SER zones, and SHALL NOT create any ticket.

#### Scenario: Handler is invoked but performs no action
- **WHEN** a `VehicleLocationUpdated` event is published
- **THEN** `SerTicketTriggerHandler` is invoked
- **THEN** no ticket is created, no provider is called, and no other observable state changes as a result
