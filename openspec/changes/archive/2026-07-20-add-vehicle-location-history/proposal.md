## Why

The My Vehicles page only ever shows a vehicle's single latest location, even though the backend already retains a full, append-only history of every recorded fix in `vehicle_locations`. Users lose visibility into where a vehicle has been, and have no way to review past positions without direct database access.

## What Changes

- Add a paginated location history endpoint (`GET /vehicles/{id}/locations`, offset-based, default page size 5) backed by a new `VehicleLocationRepository.list_history` method and a `ListVehicleLocationHistory` use case.
- Add a `VehicleLocationHistoryModal`, opened by clicking the location line on a `VehicleCard`, showing:
  - A small Leaflet map with one pin per loaded location, connected by a polyline in chronological order, with the newest pin visually distinguished (different icon/color) from older ones.
  - Clicking a pin opens a popup showing that location's `recorded_at` timestamp.
  - A list of the same locations (newest first) pairing each entry with its timestamp and coordinates.
  - A "Load more" control that fetches the next page (offset += 5) and appends both new pins/polyline points and new list rows.
- The existing shared overview map (`VehicleMap`, all vehicles at once) on `MyVehiclesPage` is unchanged.
- No vehicle selector inside the modal: the vehicle is already determined by which card was clicked.

## Capabilities

### New Capabilities
- `vehicle-location-history-ui`: the location history modal — map with numbered/connected pins, newest-pin distinction, paired list, and load-more pagination, scoped to a single vehicle.

### Modified Capabilities
- `vehicle-location-query`: add a paginated `GET /vehicles/{id}/locations` endpoint and a `list_history` method on `VehicleLocationRepository`, alongside the existing `get_latest`/`get_previous`/`save`.
- `vehicle-management-ui`: the vehicle card's location line becomes clickable and opens the new history modal instead of being static text.

## Impact

- Backend: `VehicleLocationRepository` port + Postgres implementation, new use case, new router endpoint, new response schema, ownership/auth checks mirroring the existing `GET /vehicles/{id}/location` endpoint.
- Frontend: new `VehicleLocationHistoryModal` component, new API client function for the paginated endpoint, `VehicleCard` gains an `onViewHistory`-style trigger, `MyVehiclesPage` gains modal open/close state following the existing `AddVehicleModal`/`EditVehicleModal` pattern.
- No schema/migration changes — `vehicle_locations` table already supports this.
