## Why

Users currently register vehicles under a single implicit owner. A user who wants a partner, family member, or colleague to monitor the same vehicle has no way to grant read access without sharing credentials. This change introduces explicit vehicle sharing so that trusted users can view a vehicle and receive its notifications while the owner retains exclusive control over destructive and write operations.

## What Changes

- Introduce an explicit **vehicle owner** concept by renaming `Vehicle.user_id` to `Vehicle.owner_id` and adding a `vehicle_shares` many-to-many relationship.
- Allow an owner to share a vehicle with another registered user by email; sharing is immediate, idempotent, supports many sharees per vehicle, and is revocable by the owner or the sharee. Share endpoints are rate-limited.
- Extend vehicle read access to owners and sharees; hide brand-specific configuration (Toyota credentials, generic push URL) from sharees to avoid credential exposure.
- Keep application event handlers free of infrastructure observability imports by introducing a domain `MetricsCollector` port wired to OpenTelemetry in infrastructure.
- Restrict vehicle update, delete, SER parking exemption mutation, generic location submission, and SER ticket creation to the owner only.
- Extend `GET /vehicles` to return both owned and shared vehicles, with an `is_owner` flag so the UI can render the correct actions.
- Fan out vehicle-location and SER-ticket notifications to all sharees, with each recipient's own notification-type preferences governing whether they actually receive a given notification.
- Add a **Share** action to the existing `VehicleCard` widget and a new share management modal.
- Add backend and frontend test coverage that explicitly exercises the full permission matrix (owner, sharee, non-accessor) for every affected endpoint and UI action.

## Capabilities

### New Capabilities
- `vehicle-sharing`: Introduce vehicle share entity, repository, use cases, and REST endpoints for managing sharees.

### Modified Capabilities
- `vehicle-registry`: Rename the implicit ownership field from `user_id` to `owner_id`; registration continues to set the authenticated user as the owner.
- `vehicle-list`: Return vehicles owned by or shared with the authenticated user; include `is_owner` in each list item.
- `vehicle-detail`: Allow sharees to view detail; redact `config` for sharees; include `is_owner`.
- `vehicle-update`: Enforce owner-only authorization.
- `vehicle-delete`: Enforce owner-only authorization.
- `vehicle-location-query`: Allow sharees to read the latest location and location history.
- `vehicle-location-notification`: Fan out `location_moved` notifications to sharees using each sharee's own preferences.
- `ser-zone-ticket-notification`: Fan out `ser_zone_ticket_required`, `ser_ticket_created`, and `ser_ticket_creation_failed` notifications to sharees using each sharee's own preferences.
- `ser-ticket-auto-creation`: Keep automatic SER ticket creation as an owner-only action; the provider credentials and payment context belong to the owner.
- `vehicle-ser-parking-exemption`: Allow sharees to view the exemption; restrict create/replace/delete to the owner.
- `vehicle-location-manual-entry`: Restrict authenticated generic location submission to the owner.
- `vehicle-management-ui`: Add share management affordances to `VehicleCard`; hide owner-only actions for sharees.

## Impact

- **Database**: Alembic migration to rename `vehicles.user_id` → `owner_id` and create `vehicle_shares(vehicle_id, user_id, created_at)`.
- **Domain**: New `VehicleShare` entity; `Vehicle.user_id` becomes `owner_id`.
- **Application**: New use cases `ShareVehicle`, `RevokeVehicleShare`, `ListVehicleShares`; updated `ListUserVehicles`; notification handlers iterate over recipients.
- **Infrastructure**: New Postgres repository for vehicle shares; updated vehicle repository queries.
- **Presentation**: New endpoints under `/vehicles/{id}/shares`; refactored authorization dependencies (`require_vehicle_access` / `require_vehicle_owner`); `config` redaction in responses.
- **Frontend**: `VehicleCard` share action, new `ShareVehicleModal`, `VehicleListItem`/`VehicleDetail` schema updates.
- **Tests**: Unit, application, integration, and presentation tests for sharing and authorization, including an explicit backend permission-matrix test suite that verifies every read endpoint accepts owners and sharees while every write/destructive endpoint rejects sharees and non-accessors, plus frontend tests that verify the same matrix in `VehicleCard` and `ShareVehicleModal`.
