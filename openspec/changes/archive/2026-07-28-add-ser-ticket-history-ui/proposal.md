## Why

Users currently have no way to see, from the app, which SER tickets exist for their vehicle — whether created automatically by the app or manually — where each one was for, and when it started and ends. The vehicle list already offers a "View history" button for location history; there is no equivalent for SER tickets, so users must check the provider's own app or their notifications to confirm what's happened.

## What Changes

- Add `latitude`, `longitude`, and `auto_created` (nullable boolean) columns to `parking_tickets` (migration), and populate them on every ticket-creation path going forward. Historical rows keep `auto_created=NULL`/unpopulated coordinates, matching the existing precedent for `city_code`/`zone_number`. A boolean is sufficient because there are only ever two ticket-creation paths (manual endpoint, automatic trigger) and no third is planned.
- `CreateSerTicket.execute` persists the resolved location's coordinates onto the created `ParkingTicket` and accepts an `auto_created` flag (defaulting to `False`, so the existing `POST /parking/ser-tickets` flow is unaffected); `SerTicketCreationTriggerHandler` passes `auto_created=True`.
- New `GET /vehicles/{vehicle_id}/ser-tickets` endpoint (paginated, same `limit`/`offset`/`has_more` shape as `GET /vehicles/{id}/locations`), returning **all** tickets for the vehicle (both manually and automatically created), each with start date (`created_at`), end date, latitude, longitude, city (resolved to display name), zone number, and the `auto_created` flag so the UI can label each one.
- `GET /vehicles` gains a `has_ser_tickets` boolean per vehicle (`true` if the vehicle has any ticket at all, regardless of `auto_created`), so the new button can be hidden with no extra per-card fetch — mirroring how `location` already gates the "View history" button.
- New "View SER tickets" button on `VehicleCard`, shown only when `has_ser_tickets` is `true`, opening a new `VehicleSerTicketHistoryModal`.
- The new modal renders a small Leaflet map per ticket with a single marker (no polyline, no directional arrows — there is no movement to show), plus the ticket's start date, end date, city, SER zone, and a label indicating whether it was created automatically or manually. Reuses the map scaffold/style from `VehicleLocationHistoryModal` (tile layer, marker styling, container sizing) without its polyline/bearing/arrow logic.
- All new UI strings (button label, modal title, empty/loading/error states, field labels, auto/manual label) added to both `en` and `es` translation files.

## Capabilities

### New Capabilities
- `ser-ticket-query`: backend capability exposing a paginated, vehicle-scoped SER ticket list (`GET /vehicles/{vehicle_id}/ser-tickets`, all tickets, each tagged `auto_created`) with resolved city display name.
- `ser-ticket-history-ui`: frontend capability for the "View SER tickets" button and its single-point-map modal, i18n'd, showing every ticket with an auto/manual indicator.

### Modified Capabilities
- `ser-ticket-provider`: `ParkingTicket` entity, `parking_tickets` table, and `CreateSerTicket.execute` gain `latitude`, `longitude`, and `auto_created` fields/behavior.
- `ser-ticket-auto-creation`: `SerTicketCreationTriggerHandler` now passes `auto_created=True` when calling `CreateSerTicket.execute`.
- `vehicle-list`: `GET /vehicles` response items gain a `has_ser_tickets` field.

## Impact

- **Domain**: `ParkingTicket` entity (`src/mobility_manager/domain/entities/parking_ticket.py`).
- **Infrastructure**: `parking_tickets` ORM table + new migration; `ParkingTicketRepository` gains a paginated tickets-by-vehicle query (unfiltered by `auto_created`); vehicle repository/query gains an existence check for `has_ser_tickets`.
- **Application**: `CreateSerTicket` use case; new `ListSerTickets` (or similarly named) use case.
- **Presentation**: new `GET /vehicles/{vehicle_id}/ser-tickets` route; `GET /vehicles` response schema change; new Pydantic response schemas.
- **Frontend**: `VehicleCard.tsx`, `MyVehiclesPage.tsx`, new `VehicleSerTicketHistoryModal.tsx`, `frontend/src/api/vehicles.ts`, `frontend/src/types/vehicle.ts`, `frontend/public/locales/{en,es}/translation.json`.
