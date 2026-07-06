## ADDED Requirements

### Requirement: NotificationDispatchHandler notifies a vehicle's owner on meaningful movement
The system SHALL define `NotificationDispatchHandler` as the real subscriber to `VehicleLocationUpdated`, replacing its prior no-op scaffolding. On each event, it SHALL:
1. Look up the `Vehicle` for `event.vehicle_id`. If no such vehicle exists, it SHALL skip silently (no notification, no error).
2. Look up the vehicle's previous recorded location via `VehicleLocationRepository.get_previous(event.vehicle_id, before=event.recorded_at)`. If `None` (this is the vehicle's first-ever recorded location), it SHALL skip silently.
3. Compute the distance in metres between the previous location and the event's coordinates. If this distance is less than the configured movement threshold, it SHALL skip silently — no notification is sent.
4. If the distance meets or exceeds the threshold, it SHALL look up the vehicle owner's preferences, render a localized "vehicle moved" message including the vehicle's license plate (falling back to the default language if `notification_language` is unset), and call `SendNotification.execute` with a `NotificationMessage` whose `location` is the event's coordinates.

This capability does not implement per-event-type opt-in/opt-out — a user with any `preferred_notification_channel` connected receives this notification kind unconditionally whenever the threshold is met.

#### Scenario: Movement past the threshold triggers a notification
- **WHEN** a `VehicleLocationUpdated` event's coordinates are at least the configured movement threshold away from the vehicle's previous recorded location
- **THEN** `SendNotification.execute` is called for the vehicle owner with a message containing the vehicle's license plate and a `location` equal to the event's coordinates

#### Scenario: Movement below the threshold does not trigger a notification
- **WHEN** a `VehicleLocationUpdated` event's coordinates are less than the configured movement threshold away from the vehicle's previous recorded location
- **THEN** `SendNotification.execute` is not called

#### Scenario: A vehicle's first-ever recorded location does not trigger a notification
- **WHEN** a `VehicleLocationUpdated` event is published for a vehicle with no prior recorded location
- **THEN** `SendNotification.execute` is not called

#### Scenario: A vehicle that no longer exists is skipped without error
- **WHEN** a `VehicleLocationUpdated` event references a `vehicle_id` with no matching `Vehicle`
- **THEN** the handler completes without raising and without calling `SendNotification.execute`

#### Scenario: Message is localized to the owner's notification language
- **WHEN** movement past the threshold triggers a notification for an owner whose `notification_language` is `"es"`
- **THEN** the message text is rendered in Spanish

#### Scenario: Message falls back to the default language when unset
- **WHEN** movement past the threshold triggers a notification for an owner with no `notification_language` set
- **THEN** the message text is rendered in the default language

### Requirement: Movement threshold is configurable via NOTIFICATION_MOVEMENT_THRESHOLD_METERS
The system SHALL read the minimum movement distance (in metres) that triggers a location notification from the `NOTIFICATION_MOVEMENT_THRESHOLD_METERS` environment variable, defaulting to `50` when unset.

#### Scenario: Default threshold applies when unset
- **WHEN** `NOTIFICATION_MOVEMENT_THRESHOLD_METERS` is not set in the environment
- **THEN** the system uses `50` metres as the movement threshold

#### Scenario: Configured threshold overrides the default
- **WHEN** `NOTIFICATION_MOVEMENT_THRESHOLD_METERS` is set to a specific value in the environment
- **THEN** the system uses that value as the movement threshold
