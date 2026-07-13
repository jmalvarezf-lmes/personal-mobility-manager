## MODIFIED Requirements

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
