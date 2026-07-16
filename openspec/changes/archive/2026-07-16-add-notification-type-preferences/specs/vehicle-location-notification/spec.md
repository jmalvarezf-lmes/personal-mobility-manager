## MODIFIED Requirements

### Requirement: NotificationDispatchHandler notifies a vehicle's owner on meaningful movement
The system SHALL define `NotificationDispatchHandler` as the real subscriber to `VehicleLocationUpdated`. On each event, it SHALL:
1. Look up the `Vehicle` for `event.vehicle_id`. If no such vehicle exists, it SHALL skip silently (no notification, no error).
2. Look up the vehicle owner's `location_moved` notification preference. If the preference row is missing or `enabled=false`, it SHALL skip silently — before performing any previous-location lookup.
3. Look up the vehicle's previous recorded location via `VehicleLocationRepository.get_previous(event.vehicle_id, before=event.recorded_at)`. If `None` (this is the vehicle's first-ever recorded location), it SHALL skip silently.
4. Compute the distance in metres between the previous location and the event's coordinates. Resolve the effective threshold as the user's `location_moved` preference `config.threshold_m` if set, otherwise `DEFAULT_NOTIFICATION_MOVEMENT_THRESHOLD_METERS`. If the distance is less than this threshold, it SHALL skip silently — no notification is sent.
5. If the distance meets or exceeds the threshold, it SHALL look up the vehicle owner's preferences, render a localized "vehicle moved" message including the vehicle's license plate (falling back to the default language if `notification_language` is unset), and call `SendNotification.execute` with a `NotificationMessage` whose `location` is the event's coordinates.

#### Scenario: Disabled preference skips before any location lookup
- **WHEN** a `VehicleLocationUpdated` event is published for a vehicle whose owner has `location_moved` `enabled=false`
- **THEN** `SendNotification.execute` is not called
- **THEN** `VehicleLocationRepository.get_previous` is not called

#### Scenario: Movement past the effective threshold triggers a notification
- **WHEN** a `VehicleLocationUpdated` event's coordinates are at least the owner's effective `location_moved` threshold away from the vehicle's previous recorded location
- **THEN** `SendNotification.execute` is called for the vehicle owner with a message containing the vehicle's license plate and a `location` equal to the event's coordinates

#### Scenario: Movement below the effective threshold does not trigger a notification
- **WHEN** a `VehicleLocationUpdated` event's coordinates are less than the owner's effective `location_moved` threshold away from the vehicle's previous recorded location
- **THEN** `SendNotification.execute` is not called

#### Scenario: A vehicle's first-ever recorded location does not trigger a notification
- **WHEN** a `VehicleLocationUpdated` event is published for a vehicle with no prior recorded location and the owner's `location_moved` preference is enabled
- **THEN** `SendNotification.execute` is not called

#### Scenario: A vehicle that no longer exists is skipped without error
- **WHEN** a `VehicleLocationUpdated` event references a `vehicle_id` with no matching `Vehicle`
- **THEN** the handler completes without raising and without calling `SendNotification.execute`

#### Scenario: Message is localized to the owner's notification language
- **WHEN** movement past the effective threshold triggers a notification for an owner whose `notification_language` is `"es"`
- **THEN** the message text is rendered in Spanish

#### Scenario: Message falls back to the default language when unset
- **WHEN** movement past the effective threshold triggers a notification for an owner with no `notification_language` set
- **THEN** the message text is rendered in the default language

## REMOVED Requirements

### Requirement: Movement threshold is configurable via NOTIFICATION_MOVEMENT_THRESHOLD_METERS
**Reason**: Replaced by per-user, per-type preference configuration. The movement threshold is no longer a single global on/off value read directly by the handler — it is now a per-user `location_moved.config.threshold_m` value, falling back to `DEFAULT_NOTIFICATION_MOVEMENT_THRESHOLD_METERS` when unset. See the `notification-type-preferences` capability.
**Migration**: Deployments SHALL rename the `NOTIFICATION_MOVEMENT_THRESHOLD_METERS` environment variable to `DEFAULT_NOTIFICATION_MOVEMENT_THRESHOLD_METERS`. Until renamed, the fallback default is `50`, matching the prior behavior for any user who has not customized their threshold.
