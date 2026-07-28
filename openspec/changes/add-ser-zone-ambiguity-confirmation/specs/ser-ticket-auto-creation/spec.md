## MODIFIED Requirements

### Requirement: SerTicketCreationTriggerHandler creates a SER ticket when required and auto-creation is enabled
When a `VehicleLocationUpdated` event is published, `SerTicketCreationTriggerHandler` SHALL:
1. Look up the `Vehicle` for `event.vehicle_id`. If no such vehicle exists, it SHALL skip silently (no ticket creation, no error).
2. Skip silently if the owner's `UserPreferences.auto_create_ticket` is not `true` — this handler only ever acts when it is.
3. Look up the vehicle's previous recorded location via `VehicleLocationRepository.get_previous`. If not `None`, compute the distance to the event's coordinates. If that distance is below the fixed GPS-noise floor resolved by `get_ser_ticket_creation_zone_change_floor_meters()` (default 10 meters, technical/environment-only, not a user preference), it SHALL skip silently without looking up any zone. Otherwise, resolve the SER zone containing the previous location and the SER zone containing the event's coordinates via `FindContainingSerZone`, and compare them by `(city_code, zone_number)` (treating "no containing zone" as its own distinct state). If the two zones are the same, it SHALL skip silently — the vehicle moved, but did not change SER zone, so no ticket action is needed. A vehicle's first-ever recorded location (no previous location at all) does NOT skip this step and always proceeds to the zone-requirement check below, since there is no previous zone to compare against.
4. Resolve every SER zone matching the event's coordinates via `SerZoneRepository.find_all_containing()` (see the modified `ser-zone-query` requirement) as `candidates`. Check whether a ticket is currently required via `DetermineSerTicketRequirement.execute(candidates[0] if candidates else None, event.vehicle_id)` — unchanged from `ser-zone-ticket-notification`, including exemption handling and the active-ticket idempotency short-circuit, which is scoped to the zone being checked (see the `ser-ticket-requirement` capability): an active ticket for the *same* zone still suppresses creation, but an active ticket for a *different* zone no longer does. If not required, skip silently.
5. If required and `len(candidates) == 1`, resolve the provider as the first entry of `UserSerProviderConfigRepository.list_connected_providers(owner.user_id)` and call `CreateSerTicket.execute(user_id=owner.user_id, vehicle_id=event.vehicle_id, provider=<resolved provider>, duration_minutes=owner's default_ticket_duration_minutes, location=GeoLocation(lat=event.latitude, lng=event.longitude))` — the event's own coordinates, not a fresh location lookup.
6. If required and `len(candidates) > 1`, it SHALL NOT call `CreateSerTicket.execute` — instead it defers to the zone-confirmation flow (see the `ser-zone-ambiguity-confirmation` capability's "SerTicketCreationTriggerHandler defers to a pending confirmation when the matched zone is ambiguous" requirement).
7. On a direct creation's success, publish `SerTicketCreated` carrying the vehicle id, user id, the zone's number, the created ticket's `created_at` as `start_date`, and the created ticket's `end_date`.
8. On any exception raised by a direct `CreateSerTicket.execute` call, publish `SerTicketCreationFailed` carrying the vehicle id, user id, the zone's number, and a closed-vocabulary `reason` derived from the exception type — never the raw exception message or `str(exc)`.

The entire handler body SHALL be wrapped in a broad try/except so a failure here never breaks the caller or blocks `SerTicketNotificationTriggerHandler` from running for the same event, matching the sibling handler's existing convention.

#### Scenario: Ticket created directly when required, unambiguous, and the vehicle changed SER zone
- **WHEN** `DetermineSerTicketRequirement` returns `True` for the primary zone containing a `VehicleLocationUpdated` event's coordinates, exactly one zone matches those coordinates, the owner's `auto_create_ticket` is `true`, and that zone differs from the zone containing the vehicle's previous recorded location (or there is no previous location)
- **THEN** `CreateSerTicket.execute` is called with the resolved provider, the owner's `default_ticket_duration_minutes`, and the event's coordinates as `location`
- **THEN** `SerTicketCreated` is published on success

#### Scenario: Ambiguous zone match defers to a pending confirmation instead of creating directly
- **WHEN** `DetermineSerTicketRequirement` returns `True` for the primary zone and more than one zone matches the event's coordinates within the configured containment tolerance
- **THEN** `CreateSerTicket.execute` is not called directly by this handler
- **THEN** neither `SerTicketCreated` nor `SerTicketCreationFailed` is published directly by this handler for this event

#### Scenario: No creation when auto_create_ticket is disabled
- **WHEN** a `VehicleLocationUpdated` event is published for a vehicle whose owner has `auto_create_ticket=false`
- **THEN** `CreateSerTicket.execute` is not called
- **THEN** neither `SerTicketCreated` nor `SerTicketCreationFailed` is published

#### Scenario: Movement below the GPS-noise floor skips both zone lookups
- **WHEN** a `VehicleLocationUpdated` event's coordinates are closer to the vehicle's previous recorded location than `get_ser_ticket_creation_zone_change_floor_meters()`'s resolved value
- **THEN** `FindContainingSerZone.execute` is not called for either location and `CreateSerTicket.execute` is not called

#### Scenario: Movement past the noise floor but within the same SER zone skips creation
- **WHEN** a `VehicleLocationUpdated` event's coordinates are farther from the vehicle's previous recorded location than the GPS-noise floor, and the SER zone containing the event's coordinates is the same `(city_code, zone_number)` as the SER zone containing the previous recorded location
- **THEN** `CreateSerTicket.execute` is not called

#### Scenario: Transitioning out of all SER zones skips creation
- **WHEN** the vehicle's previous recorded location was inside a SER zone and the event's coordinates are inside no SER zone (a zone transition, since the two states differ)
- **THEN** `DetermineSerTicketRequirement.execute` is called with `zone=None`, returns `False` via its existing zone-is-None short-circuit, and `CreateSerTicket.execute` is not called

#### Scenario: No ticket required outside all zones
- **WHEN** `DetermineSerTicketRequirement.execute(candidates[0] if candidates else None, event.vehicle_id)` returns `False` (the location is outside all SER zones, or enforcement is not currently active)
- **THEN** `CreateSerTicket.execute` is not called

#### Scenario: Zone changed away from an existing ticket's zone still creates a new ticket
- **WHEN** the vehicle has an active `ParkingTicket` whose `(city_code, zone_number)` is for zone A, and the event's coordinates are in a different, unambiguous zone B that requires a ticket (enforcement active, no exemption)
- **THEN** `DetermineSerTicketRequirement.execute` does not short-circuit on the existing active ticket for zone A, and `CreateSerTicket.execute` is called for zone B

#### Scenario: A matching vehicle exemption suppresses ticket creation
- **WHEN** `DetermineSerTicketRequirement.execute(candidates[0] if candidates else None, event.vehicle_id)` returns `False` because the vehicle has a stored exemption matching the primary zone's `(city_code, zone_number)`
- **THEN** `CreateSerTicket.execute` is not called, the same as any other "no ticket required" outcome — the alternates, if any, are never considered

#### Scenario: A vehicle that no longer exists is skipped without error
- **WHEN** a `VehicleLocationUpdated` event references a `vehicle_id` with no matching `Vehicle`
- **THEN** the handler completes without raising and without calling `CreateSerTicket.execute`

#### Scenario: Provider failure is translated into SerTicketCreationFailed without the raw exception
- **WHEN** a direct `CreateSerTicket.execute` call raises any exception (e.g. `SerProviderSessionNotFoundError`, `SerZoneNotFoundError`, `SerProviderVehicleNotFoundError`, `SerProviderApiError`)
- **THEN** `SerTicketCreationFailed` is published with a closed-vocabulary `reason`
- **THEN** the raw exception message is not included on the published event
