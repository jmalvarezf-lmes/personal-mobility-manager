## 1. Database migration

- [x] 1.1 Create Alembic migration to rename `vehicles.user_id` to `vehicles.owner_id`.
- [x] 1.2 Create `vehicle_shares` table with `(vehicle_id, user_id)` composite primary key, FKs to `vehicles(id)` and `users(id)` both `ON DELETE CASCADE`, and `created_at` column.
- [x] 1.3 Run migration against the local docker-compose Postgres and verify schema.

## 2. Domain layer

- [x] 2.1 Rename `Vehicle.user_id` to `Vehicle.owner_id` and update all references in domain, application, infrastructure, and tests.
- [x] 2.2 Add `VehicleShare` domain entity with `vehicle_id`, `user_id`, and `created_at` fields.
- [x] 2.3 Add `VehicleAccess` value object with `vehicle` and `is_owner` fields.
- [x] 2.4 Add `VehicleShareRepository` port with `save`, `find_by_vehicle_and_user`, `list_sharees`, `delete`, and `list_vehicle_ids_for_user` methods.
- [x] 2.5 Add `find_by_email(email: str) -> User | None` to `UserRepository` port.

## 3. Application layer

- [x] 3.1 Create `ShareVehicle` use case: validate owner, resolve sharee by email, enforce owner-not-self and existing-user rules, idempotently save share.
- [x] 3.2 Create `RevokeVehicleShare` use case: allow owner or self to delete a share row.
- [x] 3.3 Create `ListVehicleShares` use case: return sharee details for a vehicle, owner-only.
- [x] 3.4 Update `ListUserVehicles` to return owned vehicles plus shared vehicles, each tagged with `is_owner`.
- [x] 3.5 Update `UpdateVehicle`, `DeleteVehicle`, `SetVehicleSerParkingExemption`, `ClearVehicleSerParkingExemption`, and generic location submission to enforce owner-only authorization (presentation layer).
- [x] 3.6 Update `NotificationDispatchHandler` to fan out `location_moved` notifications to owner and sharees using each recipient's own preference.
- [x] 3.7 Update `SerTicketNotificationTriggerHandler` to fan out `ser_zone_ticket_required`, `ser_ticket_created`, and `ser_ticket_creation_failed` notifications to owner and sharees using each recipient's own preference.

## 4. Infrastructure layer

- [x] 4.1 Implement `PostgresVehicleShareRepository` with the required port methods.
- [x] 4.2 Update `PostgresVehicleRepository` to use `owner_id` instead of `user_id` and rename `get_all_by_user_id` to `get_all_by_owner_id`.
- [x] 4.3 Implement `find_by_email` in `PostgresUserRepository`.
- [x] 4.4 Wire the new repository and use cases into the application lifespan / dependency injection.

## 5. Presentation layer

- [x] 5.1 Refactor `deps.py` to add `require_vehicle_access` (read: owner or sharee) and `require_vehicle_owner` (write: owner only), preserving body-then-auth ordering for routes with request bodies.
- [x] 5.2 Update `GET /vehicles` to return owned + shared vehicles with `is_owner`.
- [x] 5.3 Update `GET /vehicles/{id}` to allow sharees and redact `config` for non-owners.
- [x] 5.4 Update read endpoints (`/location`, `/locations`, `/ser-tickets`, `/ser-parking-exemptions`) to use `require_vehicle_access`.
- [x] 5.5 Update write endpoints (`PUT`, `DELETE`, `/locations`, `/ser-parking-exemptions`) to use `require_vehicle_owner`.
- [x] 5.6 Add `POST /vehicles/{id}/shares`, `GET /vehicles/{id}/shares`, and `DELETE /vehicles/{id}/shares/{user_id}` endpoints.
- [x] 5.7 Update Pydantic response schemas to include `is_owner` and a redacted config variant.
- [x] 5.8 Ensure `POST /parking/ser-tickets` (manual ticket creation) enforces owner-only access if it currently checks vehicle ownership.

## 6. Frontend

- [x] 6.1 Update `VehicleListItem` and `VehicleDetail` TypeScript types to include `is_owner` and the redacted config shape.
- [x] 6.2 Update `VehicleCard` to conditionally render Edit, Delete, Share, and Set location buttons only when `is_owner` is true.
- [x] 6.3 Hide brand-specific config sections in `VehicleCard` and `EditVehicleModal` when `is_owner` is false.
- [x] 6.4 Create `ShareVehicleModal` component with email input, current sharee list, and remove actions.
- [x] 6.5 Add `shareVehicle`, `listVehicleShares`, and `revokeVehicleShare` API functions in `frontend/src/api/vehicles.ts`.
- [x] 6.6 Update translations for new share-related labels.

## 7. Tests

- [x] 7.1 Add unit tests for `VehicleShare`, `VehicleAccess`, and the new share use cases.
- [x] 7.2 Add application tests for `ListUserVehicles` with owned and shared vehicles.
- [x] 7.3 Add integration tests for `PostgresVehicleShareRepository` and the `owner_id` migration.
- [x] 7.4 Add a backend permission-matrix test suite that systematically asserts each affected endpoint (`GET /vehicles`, `GET /vehicles/{id}`, `GET /vehicles/{id}/location`, `GET /vehicles/{id}/locations`, `GET /vehicles/{id}/ser-tickets`, `GET /vehicles/{id}/ser-parking-exemptions`, `PUT /vehicles/{id}`, `DELETE /vehicles/{id}`, `POST /vehicles/{id}/locations`, `POST /vehicles/{id}/ser-parking-exemptions`, `DELETE /vehicles/{id}/ser-parking-exemptions`, `POST /vehicles/{id}/shares`, `GET /vehicles/{id}/shares`, `DELETE /vehicles/{id}/shares/{user_id}`) behaves correctly for owner, sharee, and non-accessor.
- [x] 7.5 Add notification handler tests verifying independent per-recipient preference checks and fan-out behavior.
- [x] 7.6 Add frontend permission-matrix tests that assert `VehicleCard` shows/hides Edit, Delete, Share, Set location, and View history based on `is_owner` and shared status.
- [x] 7.7 Add frontend tests for `ShareVehicleModal` flows (add by email, unknown email error, remove sharee, self-revoke).
- [x] 7.8 Run `make test` and `make coverage`; ensure domain coverage stays at 100% and application coverage at 80%.
