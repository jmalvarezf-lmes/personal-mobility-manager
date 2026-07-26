## MODIFIED Requirements

### Requirement: DetermineSerTicketRequirement use case
The system SHALL implement a `DetermineSerTicketRequirement` application use case with `execute(zone: SerZone | None, vehicle_id: UUID, at: datetime) -> bool`, returning whether a ticket is currently required for the given vehicle located in `zone` at time `at`. The use case SHALL accept an injected enforcement-schedule dependency (see the `ser-enforcement-schedule` capability's `SerEnforcementSchedule`), an injected `ParkingTicketRepository` dependency, an injected `VehicleAmbientLabelRepository` dependency (see the `ambient-label` capability), an injected `SerLabelExemptionRule` dependency (see the `ser-label-exemption-rule` capability), an injected `VehicleSerParkingExemptionRepository` dependency (see the `vehicle-ser-parking-exemption` capability), and an injected `SerExemptionZoneRule` dependency (see the `ser-exemption-zone-rule` capability) via its constructor.

`execute(zone, vehicle_id, at)` SHALL return `False` immediately when `zone` is `None`, without consulting any injected dependency. When `zone` is not `None`, it SHALL return `False` if the injected enforcement-schedule dependency's `is_active_now(zone.city_code)` returns `False`, without consulting the ticket repository, the ambient-label repository, the label-exemption rule, the manual-exemption repository, or the zone rule. Otherwise, it SHALL return `False` if `ParkingTicketRepository.find_active_for_vehicle(vehicle_id, at)` returns a ticket, without consulting the ambient-label repository, the label-exemption rule, the manual-exemption repository, or the zone rule.

Otherwise, it SHALL look up the vehicle's ambient label via `VehicleAmbientLabelRepository.get_by_vehicle_id(vehicle_id)`. If that lookup returns a row whose `status == AmbientLabelStatus.FOUND` and the injected `SerLabelExemptionRule` dependency's `is_label_exempt(zone.city_code, label)` returns `True`, it SHALL return `False` immediately, without consulting the manual-exemption repository or the zone rule. Any other ambient-label outcome — no row (`None`), or a row whose `status` is `NOT_FOUND` or `ERROR` — SHALL be treated as "not exempt via label" and SHALL fall through to the manual-exemption check below, without itself causing a `True` or `False` return.

Otherwise (no label exemption applies), it SHALL look up the vehicle's exemption via `VehicleSerParkingExemptionRepository.find_by_vehicle_id(vehicle_id)`; if no exemption exists, or its `(city_code, zone_number)` does not equal `(zone.city_code, zone.zone_number)`, it SHALL return `True` without consulting the zone rule. Otherwise (a matching exemption exists), it SHALL return `True` unless the injected `SerExemptionZoneRule` dependency's `is_zone_eligible(zone)` returns `True`, in which case it SHALL return `False`. Home-proximity logic remains an unevaluated seam for future changes.

#### Scenario: Ticket required when inside a zone during enforcement hours with no exemption and no electric label
- **WHEN** `DetermineSerTicketRequirement.execute(zone, vehicle_id, at)` is called with a non-`None` `SerZone`, the injected enforcement-schedule dependency's `is_active_now(zone.city_code)` returns `True`, the vehicle has no active ticket, the vehicle's ambient-label lookup does not resolve to an exempt label, and the vehicle has no matching exemption
- **THEN** it returns `True`, without consulting the injected `SerExemptionZoneRule` dependency

#### Scenario: No ticket required when outside all zones
- **WHEN** `DetermineSerTicketRequirement.execute(zone, vehicle_id, at)` is called with `zone=None`
- **THEN** it returns `False`, without consulting the injected enforcement-schedule dependency, the ticket repository, the ambient-label repository, the label-exemption rule, the manual-exemption repository, or the zone rule

#### Scenario: No ticket required when inside a zone but outside enforcement hours
- **WHEN** `DetermineSerTicketRequirement.execute(zone, vehicle_id, at)` is called with a non-`None` `SerZone` and the injected enforcement-schedule dependency's `is_active_now(zone.city_code)` returns `False` (e.g. it is a Sunday, a holiday, or outside today's operating hours)
- **THEN** it returns `False`, without consulting the ticket repository, the ambient-label repository, the label-exemption rule, the manual-exemption repository, or the zone rule

#### Scenario: No ticket required when the vehicle already has an active ticket
- **WHEN** `DetermineSerTicketRequirement.execute(zone, vehicle_id, at)` is called with a non-`None` `SerZone`, enforcement is active, and `ParkingTicketRepository.find_active_for_vehicle(vehicle_id, at)` returns a ticket
- **THEN** it returns `False`, without consulting the ambient-label repository, the label-exemption rule, the manual-exemption repository, or the zone rule

#### Scenario: No ticket required when the vehicle's ambient label is confirmed electric and exempt in that city
- **WHEN** `DetermineSerTicketRequirement.execute(zone, vehicle_id, at)` is called with a non-`None` `SerZone`, enforcement is active, the vehicle has no active ticket, `VehicleAmbientLabelRepository.get_by_vehicle_id(vehicle_id)` returns a row with `status == AmbientLabelStatus.FOUND` and `label == AmbientLabel.ZERO`, and the injected `SerLabelExemptionRule` dependency's `is_label_exempt(zone.city_code, label)` returns `True`
- **THEN** it returns `False`, without consulting the manual-exemption repository or the injected `SerExemptionZoneRule` dependency

#### Scenario: Ticket-requirement falls through to the manual exemption check when the ambient label is not found
- **WHEN** `DetermineSerTicketRequirement.execute(zone, vehicle_id, at)` is called with a non-`None` `SerZone`, enforcement is active, the vehicle has no active ticket, and `VehicleAmbientLabelRepository.get_by_vehicle_id(vehicle_id)` returns `None`, or a row whose `status` is `AmbientLabelStatus.NOT_FOUND` or `AmbientLabelStatus.ERROR`
- **THEN** the ambient-label lookup does not itself determine the result, and the use case proceeds to evaluate the manual-exemption repository as if no label exemption applied

#### Scenario: No ticket required when the vehicle has a matching exemption and the zone rule accepts the zone
- **WHEN** `DetermineSerTicketRequirement.execute(zone, vehicle_id, at)` is called with a non-`None` `SerZone`, enforcement is active, the vehicle has no active ticket, no label exemption applies, `VehicleSerParkingExemptionRepository.find_by_vehicle_id(vehicle_id)` returns an exemption whose `(city_code, zone_number)` equals `(zone.city_code, zone.zone_number)`, and the injected `SerExemptionZoneRule` dependency's `is_zone_eligible(zone)` returns `True`
- **THEN** it returns `False`

#### Scenario: Ticket still required when the vehicle has a matching exemption but the zone rule rejects the zone
- **WHEN** `DetermineSerTicketRequirement.execute(zone, vehicle_id, at)` is called with a non-`None` `SerZone`, enforcement is active, the vehicle has no active ticket, no label exemption applies, `VehicleSerParkingExemptionRepository.find_by_vehicle_id(vehicle_id)` returns an exemption whose `(city_code, zone_number)` equals `(zone.city_code, zone.zone_number)`, and the injected `SerExemptionZoneRule` dependency's `is_zone_eligible(zone)` returns `False` (e.g. a Madrid zone that is not `"Verde"`)
- **THEN** it returns `True`

#### Scenario: Ticket still required when the vehicle's exemption is for a different zone
- **WHEN** `DetermineSerTicketRequirement.execute(zone, vehicle_id, at)` is called with a non-`None` `SerZone`, enforcement is active, the vehicle has no active ticket, no label exemption applies, and the vehicle's stored exemption's `(city_code, zone_number)` does not equal `(zone.city_code, zone.zone_number)`
- **THEN** it returns `True`, without consulting the injected `SerExemptionZoneRule` dependency

#### Scenario: Home-proximity logic remains unevaluated
- **WHEN** `DetermineSerTicketRequirement.execute(zone, vehicle_id, at)` is called with a non-`None` `SerZone`
- **THEN** the result depends only on zone presence, the injected enforcement-schedule dependency's answer, active-ticket state, the vehicle's ambient label and the injected `SerLabelExemptionRule` dependency's answer, the vehicle's stored exemption, and the injected `SerExemptionZoneRule` dependency's answer, since home-proximity is not wired in during this change
