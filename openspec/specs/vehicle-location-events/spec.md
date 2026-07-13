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
The system SHALL register a `SerTicketTriggerHandler` as a subscriber to `VehicleLocationUpdated` at application startup. On each event, it SHALL:
1. Look up the vehicle's previous recorded location via `VehicleLocationRepository.get_previous(event.vehicle_id, before=event.received_at)`.
2. If a previous location exists and the distance between it and the event's coordinates is less than the configured movement threshold (`NOTIFICATION_MOVEMENT_THRESHOLD_METERS`, the same threshold and `distance_m` computation `NotificationDispatchHandler` uses), it SHALL skip silently — no zone lookup, no notification.
3. Otherwise (no previous location — the vehicle's first-ever recorded location — or the distance meets/exceeds the threshold), it SHALL check whether the event's coordinates fall inside a SER zone via `FindContainingSerZone`, and whether a ticket is currently required via `DetermineSerTicketRequirement`.
4. If a ticket is required, it SHALL look up the vehicle owner's preferences and send a localized "SER ticket required" notification via `SendNotification`, following the same owner-lookup/language-fallback pattern `NotificationDispatchHandler` uses. It SHALL NOT create a ticket or call any ticket provider.

#### Scenario: Handler skips when location is unchanged relative to the previous ping
- **WHEN** a `VehicleLocationUpdated` event's coordinates are less than the configured movement threshold away from the vehicle's previous recorded location
- **THEN** `SerTicketTriggerHandler` performs no SER zone lookup and sends no notification

#### Scenario: Handler checks zone containment on genuine movement
- **WHEN** a `VehicleLocationUpdated` event's coordinates are at least the configured movement threshold away from the vehicle's previous recorded location
- **THEN** `SerTicketTriggerHandler` calls `FindContainingSerZone` with the event's coordinates

#### Scenario: Handler checks zone containment on a vehicle's first-ever recorded location
- **WHEN** a `VehicleLocationUpdated` event is published for a vehicle with no prior recorded location
- **THEN** `SerTicketTriggerHandler` calls `FindContainingSerZone` with the event's coordinates (absence of history is not treated as "unchanged")

#### Scenario: No ticket is created and no provider is called
- **WHEN** a `VehicleLocationUpdated` event is published, regardless of zone containment result
- **THEN** no ticket is created and no ticket provider is called as a result of this handler
