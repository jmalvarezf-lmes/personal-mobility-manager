## 1. Update ElParkingClient headers

- [x] 1.1 Add `_EP_APP_OS = "web"` constant in `src/mobility_manager/infrastructure/ser_ticket_providers/elparking/client.py`, next to `_EP_APP_NAME`.
- [x] 1.2 Extend `_auth_headers()` to return `ep-app-os: web` alongside `ep-app-name` and `ep-app-version`.
- [x] 1.3 Update the module docstring to mention the three headers.

## 2. Update tests

- [x] 2.1 Update `_assert_app_headers()` in `tests/infrastructure/test_elparking_client.py` to assert `request.headers["ep-app-os"] == "web"`.
- [x] 2.2 Update the test module docstring to mention `ep-app-os`.
- [x] 2.3 Run `make test` and verify all tests pass.

## 3. Verify against live API (if possible)

- [ ] 3.1 Confirm that an ElParking login/ticket request with `ep-app-os: web` no longer fails due to an outdated `ep-app-version`.
