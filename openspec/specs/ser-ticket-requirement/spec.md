### Requirement: DetermineSerTicketRequirement use case
The system SHALL implement a `DetermineSerTicketRequirement` application use case with `execute(zone: SerZone | None, vehicle_id: UUID) -> bool`, returning whether a ticket is currently required for the given vehicle located in `zone`. The use case SHALL accept an injected enforcement-schedule dependency (see the `ser-enforcement-schedule` capability's `SerEnforcementSchedule`) and an injected `VehicleSerParkingExemptionRepository` dependency (see the `vehicle-ser-parking-exemption` capability) via its constructor. `execute(zone, vehicle_id)` SHALL return `False` immediately when `zone` is `None`, without consulting either injected dependency. When `zone` is not `None`, it SHALL return `False` if the injected enforcement-schedule dependency's `is_active_now(zone.city_code)` returns `False`, without consulting the exemption repository. Otherwise, it SHALL look up the vehicle's exemption via `VehicleSerParkingExemptionRepository.find_by_vehicle_id(vehicle_id)`; if an exemption exists and its `(city_code, zone_number)` equals `(zone.city_code, zone.zone_number)`, it SHALL return `False`. Otherwise it SHALL return `True`. Home-proximity logic remains an unevaluated seam for future changes.

#### Scenario: Ticket required when inside a zone during enforcement hours with no exemption
- **WHEN** `DetermineSerTicketRequirement.execute(zone, vehicle_id)` is called with a non-`None` `SerZone`, the injected enforcement-schedule dependency's `is_active_now(zone.city_code)` returns `True`, and the vehicle has no matching exemption
- **THEN** it returns `True`

#### Scenario: No ticket required when outside all zones
- **WHEN** `DetermineSerTicketRequirement.execute(zone, vehicle_id)` is called with `zone=None`
- **THEN** it returns `False`, without consulting the injected enforcement-schedule dependency or the exemption repository

#### Scenario: No ticket required when inside a zone but outside enforcement hours
- **WHEN** `DetermineSerTicketRequirement.execute(zone, vehicle_id)` is called with a non-`None` `SerZone` and the injected enforcement-schedule dependency's `is_active_now(zone.city_code)` returns `False` (e.g. it is a Sunday, a holiday, or outside today's operating hours)
- **THEN** it returns `False`, without consulting the exemption repository

#### Scenario: No ticket required when the vehicle has a matching exemption
- **WHEN** `DetermineSerTicketRequirement.execute(zone, vehicle_id)` is called with a non-`None` `SerZone`, enforcement is active, and `VehicleSerParkingExemptionRepository.find_by_vehicle_id(vehicle_id)` returns an exemption whose `(city_code, zone_number)` equals `(zone.city_code, zone.zone_number)`
- **THEN** it returns `False`

#### Scenario: Ticket still required when the vehicle's exemption is for a different zone
- **WHEN** `DetermineSerTicketRequirement.execute(zone, vehicle_id)` is called with a non-`None` `SerZone`, enforcement is active, and the vehicle's stored exemption's `(city_code, zone_number)` does not equal `(zone.city_code, zone.zone_number)`
- **THEN** it returns `True`

#### Scenario: Home-proximity logic remains unevaluated
- **WHEN** `DetermineSerTicketRequirement.execute(zone, vehicle_id)` is called with a non-`None` `SerZone`
- **THEN** the result depends only on zone presence, the injected enforcement-schedule dependency's answer, and the vehicle's stored exemption, since home-proximity is not wired in during this change
