## Why

Users have no way to view, manage, or delete the vehicles associated with their account after registration. Adding a protected "My Vehicles" section gives users full CRUD control over their vehicles and surfaces live location data directly in the UI.

## What Changes

- Add a new **My Vehicles** page at `/my-vehicles` (protected route, login required)
- Add a **My Vehicles** nav link visible only when the user is authenticated
- Add a shared Leaflet map at the top of the page showing all vehicles with a known location as distinct car icons
- Add vehicle cards below the map listing each vehicle with brand, config details, and CRUD actions
- Toyota vehicles display: display_name, username, locale, VIN; password shown masked with option to update
- Generic vehicles display: display_name and the constructed push URL (`<origin>/api/vehicles/{token}/location`)
- Add **list**, **get**, **update**, and **delete** vehicle API endpoints (registration already exists)
- Add an Alembic migration to set `ON DELETE CASCADE` on `vehicle_configs` and `vehicle_locations` foreign keys
- Add `get_all_by_user_id()` to the vehicle repository port and implementation
- Add `list_user_vehicles`, `delete_vehicle`, and `update_vehicle` use cases

## Capabilities

### New Capabilities

- `vehicle-management-ui`: Protected My Vehicles page with list, create, edit, and delete flows; shared map showing vehicle locations as car icons
- `vehicle-list`: `GET /vehicles` endpoint that returns all vehicles for the authenticated user, each enriched with their latest location if available
- `vehicle-detail`: `GET /vehicles/{id}` endpoint returning a single vehicle with brand-specific config (Toyota password masked)
- `vehicle-update`: `PUT /vehicles/{id}` endpoint to update display_name and brand-specific credentials
- `vehicle-delete`: `DELETE /vehicles/{id}` endpoint with ownership check; cascade handled at DB level via migration

### Modified Capabilities

- `vehicle-registry`: Adding `get_all_by_user_id()` to the repository port and list/detail/update/delete endpoints alongside the existing register endpoint
- `schema-migrations`: New migration adds `ON DELETE CASCADE` to `vehicle_configs.vehicle_id` and `vehicle_locations.vehicle_id` foreign keys

## Impact

- **Backend**: new endpoints on `routers/vehicles.py`; new use cases; new repo method; new Alembic migration
- **Frontend**: new page, API module, types, components (VehicleMap, VehicleCard, AddVehicleModal, EditVehicleModal); updated App.tsx routing and Nav.tsx
- **Dependencies**: no new packages required (react-leaflet already in use; Leaflet DivIcon for car marker)
- **Auth**: all new vehicle endpoints require a valid JWT session cookie; delete and update also verify ownership
