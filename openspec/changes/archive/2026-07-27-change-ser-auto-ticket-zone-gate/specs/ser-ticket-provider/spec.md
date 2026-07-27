## MODIFIED Requirements

### Requirement: ParkingTicket entity represents a created SER ticket
The system SHALL define a `ParkingTicket` domain entity with fields: `id` (UUID), `vehicle_id` (UUID), `user_id` (UUID), `provider` (str), `duration_minutes` (int), `provider_reference` (str or None), `cost` (float), `end_date` (datetime), `created_at` (datetime), `city_code` (str or None), `zone_number` (str or None). `city_code` and `zone_number` identify the SER zone the ticket was created for; both SHALL be populated by every ticket-creating code path going forward and SHALL only be `None` for tickets persisted before these fields were introduced (whose original zone cannot be recovered).

#### Scenario: ParkingTicket entity is immutable value object
- **WHEN** a `ParkingTicket` is constructed
- **THEN** it is a frozen dataclass (or equivalent) with all ten fields populated (`provider_reference`, `city_code`, and `zone_number` may be `None`)

#### Scenario: A newly created ticket always carries its zone
- **WHEN** a `ParkingTicket` is created via any concrete `SerTicketProviderPort.create_ticket` implementation
- **THEN** its `city_code` and `zone_number` are populated from the `SerZone` that was resolved to contain the ticket's `location`, never left `None`

---

### Requirement: ElParkingSerTicketProvider implements ticket creation against the ElParking API
`ElParkingSerTicketProvider.create_ticket` SHALL:
1. Resolve the vehicle's ElParking `id_vehicle` by matching `vehicle.license_plate` against the authenticated user's ElParking vehicle list; raise `SerProviderVehicleNotFoundError` if no match is found.
2. Resolve the SER zone containing `location` using the existing `SerZoneRepository`/`FindContainingSerZone` — ElParking is never queried for spatial containment against our own zone geometry.
3. Resolve `id_ser_town` for the zone's `city_code` via the cached ElParking city/zone/rate mapping (see the mapping-cache requirement), matching town name case-insensitively against the `cities` table.
4. Resolve `id_ser_zone` by matching the zone's `zone_number` against the cached zones' leading name number (zero-padded); when more than one cached zone matches the same `zone_number` for that town, disambiguate by testing `location` against each candidate's own polygon and selecting the containing one.
5. Resolve `id_ser_rate` by matching the resolved zone's cached rates against the zone's `zone_type` (case/accent-insensitive, ignoring a `"Tarifa "` prefix).
6. Fetch the mandatory pricing/checksum step via `ElParkingClient`, select the entry whose `stay_duration` equals `duration_minutes`, and use its `fare_qty` and the verbatim `step_request` in the final request — never constructing or altering `step_request`.
7. Submit the ticket via `ElParkingClient`, and return a `ParkingTicket` populated with the response's cost and `end_date`, and with `city_code`/`zone_number` set from the `SerZone` resolved in step 2 (no additional lookup — the same resolved zone used for id_ser_town/id_ser_zone/id_ser_rate resolution).

#### Scenario: Successful ticket creation resolves every identifier and submits the ticket
- **WHEN** `create_ticket` is called for a vehicle whose plate matches an ElParking-registered vehicle, at a location inside a known SER zone
- **THEN** the resulting ElParking request includes the vehicle's `id_vehicle`, the resolved `id_ser_zone`/`id_ser_rate`, the given `start_date`/`duration_minutes`, `location`'s coordinates, and the pricing step's verbatim `step_request`
- **THEN** the returned `ParkingTicket` has `cost` and `end_date` populated from ElParking's response, and `city_code`/`zone_number` populated from the zone resolved in step 2

#### Scenario: Vehicle not registered on ElParking's side raises a typed error
- **WHEN** `create_ticket` is called for a vehicle whose `license_plate` does not match any vehicle in the authenticated user's ElParking vehicle list
- **THEN** `SerProviderVehicleNotFoundError` is raised, and no further ElParking calls (town/zone/rate/steps/create) are made

#### Scenario: Duplicate zone_number within a town is disambiguated by polygon containment
- **WHEN** more than one cached ElParking zone shares the same `zone_number` for the resolved town
- **THEN** `create_ticket` selects the candidate whose own polygon contains `location`, not an arbitrary or first match
