## ADDED Requirements

### Requirement: Vehicle repository exposes get_all_by_user_id
The `VehicleRepository` port SHALL define `get_all_by_user_id(user_id: UUID) -> list[Vehicle]`. The `PostgresVehicleRepository` SHALL implement this method by executing a `SELECT` on `vehicles_table` filtered by `user_id`.

#### Scenario: Method exists on port
- **WHEN** `VehicleRepository` is inspected
- **THEN** `get_all_by_user_id` is defined as an abstract method with signature `(user_id: UUID) -> list[Vehicle]`

#### Scenario: Implementation returns empty list for user with no vehicles
- **WHEN** `get_all_by_user_id(user_id)` is called for a user who has no vehicles
- **THEN** the returned list is empty

#### Scenario: Implementation returns only the requesting user's vehicles
- **WHEN** two users each have registered vehicles
- **THEN** `get_all_by_user_id(user_a_id)` returns only user A's vehicles
