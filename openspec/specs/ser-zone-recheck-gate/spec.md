### Requirement: SerZoneRecheckGate decides whether a location event warrants a SER zone/requirement check
The system SHALL provide a `SerZoneRecheckGate` application-layer collaborator with a method `evaluate(event: VehicleLocationUpdated, movement_floor_meters: float) -> SerZoneRecheckDecision`, where `SerZoneRecheckDecision` carries `should_check: bool` and `zone: SerZone | None` (populated only when `should_check` is `True`). It SHALL be used by both `SerTicketCreationTriggerHandler` and `SerTicketNotificationTriggerHandler` in place of each handler's own previous-location/distance/zone-comparison logic, with each caller supplying its own `movement_floor_meters` (the two callers' floors remain independent values).

`evaluate` SHALL first call `ParkingTicketRepository.find_all_active_for_vehicle(event.vehicle_id, at=event.received_at)`. If that call returns a non-empty list (the vehicle currently holds at least one active `ParkingTicket`, regardless of which zone it covers), it SHALL apply the following skip logic:
1. If `VehicleLocationRepository.get_previous(event.vehicle_id, before=event.received_at)` returns `None` (the vehicle's first-ever recorded location), return `should_check=True` with `zone` resolved via `FindContainingSerZone.execute` for the event's coordinates.
2. Otherwise, compute the distance between the previous location and the event's coordinates. If it is below `movement_floor_meters`, return `should_check=False` with `zone=None`, without calling `FindContainingSerZone` at all.
3. Otherwise, resolve the SER zone containing the previous location and the SER zone containing the event's coordinates via `FindContainingSerZone`, compared by `(city_code, zone_number)` (`None` as its own distinct state). If they are the same, return `should_check=False` with `zone=None`. Otherwise, return `should_check=True` with the resolved current zone.

If `find_all_active_for_vehicle` returns an empty list (the vehicle holds no active `ParkingTicket` at all), `evaluate` SHALL return `should_check=True` unconditionally, with `zone` resolved via `FindContainingSerZone.execute` for the event's coordinates, regardless of distance from the previous location or whether the SER zone is unchanged.

#### Scenario: No active ticket always triggers a recheck regardless of movement
- **WHEN** `evaluate` is called for a vehicle with no active `ParkingTicket`, and the event's coordinates are identical to the vehicle's previous recorded location
- **THEN** the returned decision has `should_check=True` and `zone` set to the result of `FindContainingSerZone.execute` for the event's coordinates

#### Scenario: No active ticket always triggers a recheck even in an unchanged zone
- **WHEN** `evaluate` is called for a vehicle with no active `ParkingTicket`, and the SER zone containing the event's coordinates is the same `(city_code, zone_number)` as the zone containing the previous recorded location
- **THEN** the returned decision has `should_check=True`

#### Scenario: Active ticket held — movement below the floor skips without any zone lookup
- **WHEN** `evaluate` is called for a vehicle holding at least one active `ParkingTicket`, and the distance between the event's coordinates and the vehicle's previous recorded location is below `movement_floor_meters`
- **THEN** the returned decision has `should_check=False` and `zone=None`
- **THEN** `FindContainingSerZone.execute` is not called

#### Scenario: Active ticket held — movement past the floor but unchanged zone skips
- **WHEN** `evaluate` is called for a vehicle holding at least one active `ParkingTicket`, the distance between the event's coordinates and the previous recorded location is at or above `movement_floor_meters`, and the SER zone containing the event's coordinates is the same `(city_code, zone_number)` as the zone containing the previous recorded location
- **THEN** the returned decision has `should_check=False`

#### Scenario: Active ticket held — genuine zone change triggers a recheck
- **WHEN** `evaluate` is called for a vehicle holding at least one active `ParkingTicket`, and the SER zone containing the event's coordinates differs from the zone containing the previous recorded location
- **THEN** the returned decision has `should_check=True` with `zone` set to the zone containing the event's coordinates

#### Scenario: First-ever recorded location always triggers a recheck
- **WHEN** `evaluate` is called for a vehicle with no previous recorded location at all
- **THEN** the returned decision has `should_check=True`, regardless of whether the vehicle holds an active `ParkingTicket`

#### Scenario: Each caller's own movement floor is used, independently
- **WHEN** `SerTicketCreationTriggerHandler` and `SerTicketNotificationTriggerHandler` each call `evaluate` for the same event but pass different `movement_floor_meters` values
- **THEN** each call's skip decision is computed using only the floor value that call passed, never the other caller's value
