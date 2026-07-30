## 1. Backend endpoint

- [x] 1.1 Add `POST /vehicles/{vehicle_id}/locations` in `presentation/api/routers/vehicles.py`: depends on `get_current_user` and `get_owned_vehicle_or_raise(request, vehicle_id, current_user)`, reuses `PushLocationRequest` as the body schema.
- [x] 1.2 In the handler, return `400` if the resolved vehicle's `brand != Brand.GENERIC`.
- [x] 1.3 Call `request.app.state.record_vehicle_location.execute(vehicle_id=..., lat=body.lat, lon=body.lon, recorded_at=body.recorded_at, source="push")`, catching `ValueError` into `HTTPException(422)` exactly as `push_vehicle_location` does.
- [x] 1.4 Return `204 No Content` on success.
- [x] 1.5 Add a `_owned_vehicle_id_key(request)` rate-limit key function (keyed by `request.path_params["vehicle_id"]`, mirroring `_vehicle_token_key`) and apply `@limiter.limit("60/minute")` + `@limiter.limit("1/minute", key_func=_owned_vehicle_id_key)` to the new route.
- [x] 1.6 Update the router's module docstring endpoint list to include the new route.

## 2. Backend tests

- [x] 2.1 Unit/e2e test: authenticated owner of a generic vehicle gets `204` and a new `vehicle_locations` row with `source="push"`.
- [x] 2.2 Test: request for a vehicle owned by a different user returns `403` (deviation from tasks.md's stated `404` — see apply report: `get_owned_vehicle_or_raise`, the exact dependency design.md mandates reusing, returns 403 for non-owner/404 for not-found, matching every other owned-vehicle mutation route).
- [x] 2.3 Test: request for a Toyota vehicle (owned by the caller) returns `400`.
- [x] 2.4 Test: unauthenticated request returns `401`.
- [x] 2.5 Test: out-of-range `lat`/`lon` returns `422`.
- [x] 2.6 Test: `recorded_at` more than 60s in the future returns `422`.
- [x] 2.7 Test: a second submission for the same `vehicle_id` within 60s returns `429`; a submission for a different vehicle in the same window is unaffected.

## 3. Frontend API client

- [x] 3.1 Add `pushVehicleLocation(vehicleId, { lat, lon, recorded_at })` to `frontend/src/api/vehicles.ts`, calling `POST /vehicles/{vehicleId}/locations`.
- [x] 3.2 Add/extend tests in `frontend/src/api/vehicles.test.ts` for the new client function (success and error paths).

## 4. Frontend dialog

- [x] 4.1 Create `frontend/src/components/SetVehicleLocationModal.tsx` following the `AddVehicleModal`/`EditVehicleModal` overlay pattern (`role="dialog"`, `aria-modal`, `onClose`/`onSaved` callbacks).
- [x] 4.2 Add a "Use my current location" button that calls `navigator.geolocation.getCurrentPosition`, populating editable latitude/longitude number inputs on success; on error/denial, show an inline message and leave the fields empty/editable.
- [x] 4.3 Add editable latitude/longitude number inputs with client-side validation matching backend bounds (`[-90, 90]`, `[-180, 180]`); block submit when out of range.
- [x] 4.4 On Save, call the new `pushVehicleLocation` client function with the current field values and `recorded_at` set to the current client time; show `submitting`/`error` state consistent with the other modals.
- [x] 4.5 On success, close the modal and trigger the vehicle list/card refresh (same callback convention as `EditVehicleModal`'s `onUpdated`).
- [x] 4.6 On error (e.g. `429`), keep the modal open with an inline error message and the entered values intact.

## 5. Vehicle card integration

- [x] 5.1 In `VehicleCard.tsx`, add a "Set location" button shown only when `vehicle.brand === "generic"`, opening `SetVehicleLocationModal` scoped to that vehicle.
- [x] 5.2 Wire modal open/close state and the refresh callback into the card/list, consistent with how Edit is wired.

## 6. i18n

- [x] 6.1 Add English and Spanish strings for: the "Set location" button, modal title, "Use my current location" button, latitude/longitude field labels, geolocation error message, and validation error message.

## 7. Frontend tests

- [x] 7.1 `SetVehicleLocationModal.test.tsx`: geolocation success autofills fields; geolocation denial/error shows inline message and leaves fields editable; manual entry without geolocation submits typed values; out-of-range values block submit; save success closes modal; save failure keeps modal open with error.
- [x] 7.2 `VehicleCard.test.tsx`: "Set location" button shown for generic vehicles, absent for Toyota vehicles; clicking it opens the modal.

## 8. Docs

- [x] 8.1 Check whether `README.md` needs updating to mention the new manual/browser location entry option for generic vehicles (per project's mandatory README-consistency rule); update if so.

## 9. Fixes from 4R review

- [x] 9.1 `SetVehicleLocationModal`: call `onClose()` itself after a successful save (after `onSaved(...)`), matching `AddVehicleModal`/`EditVehicleModal`'s convention, instead of relying solely on the parent's `onSaved` callback to close it.
- [x] 9.2 `VehicleCard`: reconcile its `onSaved` handler with 9.1 so the modal isn't double-closed or left in an inconsistent state; keep `onLocationUpdated` propagation for the card's displayed location.
- [x] 9.3 `SetVehicleLocationModal.test.tsx`: fix the "closes the modal on successful save" test to actually assert the dialog is removed from the DOM, not just that `onSaved` was called.
- [x] 9.4 `VehicleCard.test.tsx`: add an integration-style test exercising the full round trip — open the Set Location modal, submit a location, assert the modal closes and the card reflects the updated location.
- [x] 9.5 `SetVehicleLocationModal`: pass a `timeout` option to `getCurrentPosition` and add a pending/disabled state on the "Use my current location" button while the geolocation request is in flight, mirroring the existing `submitting` state used for Save.
- [x] 9.6 `SetVehicleLocationModal.test.tsx`: add/update a test covering the geolocation-pending state (button disabled while awaiting position).
- [x] 9.7 Run `make test` (backend) and the frontend test suite; confirm both green. Frontend: 240/240 passed. Backend: 1099/1100 passed — 1 pre-existing failure (`test_ser_enforcement_calendar_migrations_integration.py::test_migrations_apply_cleanly_and_seed_data_matches_spec`, missing "madrid" seed row in local `cities` table) unrelated to this change; no backend files were touched by tasks 9.1–9.6.
