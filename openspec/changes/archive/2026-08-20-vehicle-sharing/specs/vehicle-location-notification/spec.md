## MODIFIED Requirements

### Requirement: NotificationDispatchHandler notifies all vehicle accessors on meaningful movement
The system SHALL define `NotificationDispatchHandler` as the real subscriber to `VehicleLocationUpdated`. On each event, it SHALL:
1. Look up the `Vehicle` for `event.vehicle_id`. If no such vehicle exists, it SHALL skip silently (no notification, no error).
2. Resolve the notification recipient list as the vehicle's `owner_id` plus the `user_id` of every active `VehicleShare` for that vehicle.
3. For each recipient, look up that recipient's own `location_moved` notification preference. If the preference row is missing or `enabled=false`, it SHALL skip that recipient silently.
4. For each recipient with the preference enabled, look up the vehicle's previous recorded location via `VehicleLocationRepository.get_previous(event.vehicle_id, before=event.recorded_at)`. If `None` (this is the vehicle's first-ever recorded location), it SHALL skip that recipient silently.
5. Compute the distance in metres between the previous location and the event's coordinates. Resolve the effective threshold as that recipient's `location_moved` preference `config.threshold_m` if set, otherwise `DEFAULT_NOTIFICATION_MOVEMENT_THRESHOLD_METERS`. If the distance is less than this threshold, skip that recipient silently.
6. If the distance meets or exceeds the threshold, look up that recipient's preferences, render a localized "vehicle moved" message including the vehicle's license plate (falling back to the default language if `notification_language` is unset), and call `SendNotification.execute` with a `NotificationMessage` whose `location` is the event's coordinates.

Each recipient SHALL be evaluated independently; one recipient's disabled preference or below-threshold setting SHALL NOT affect other recipients.

#### Scenario: Owner receives notification when preference enabled
- **WHEN** a `VehicleLocationUpdated` event is published for a vehicle whose owner has `location_moved` `enabled=true` and movement exceeds their threshold
- **THEN** `SendNotification.execute` is called for the owner

#### Scenario: Sharee receives notification when their own preference enabled
- **WHEN** a `VehicleLocationUpdated` event is published for a vehicle shared with user B, user B has `location_moved` `enabled=true`, and movement exceeds user B's threshold
- **THEN** `SendNotification.execute` is called for user B

#### Scenario: Sharee does not receive notification when their own preference disabled
- **WHEN** a `VehicleLocationUpdated` event is published for a vehicle shared with user B and user B has `location_moved` `enabled=false`
- **THEN** `SendNotification.execute` is not called for user B
- **THEN** the owner's notification behavior is unaffected

#### Scenario: Movement below a sharee's threshold skips only that sharee
- **WHEN** a `VehicleLocationUpdated` event's movement exceeds the owner's threshold but is below a sharee's threshold
- **THEN** `SendNotification.execute` is called for the owner
- **THEN** `SendNotification.execute` is not called for that sharee

#### Scenario: A vehicle that no longer exists is skipped without error
- **WHEN** a `VehicleLocationUpdated` event references a `vehicle_id` with no matching `Vehicle`
- **THEN** the handler completes without raising and without calling `SendNotification.execute`
