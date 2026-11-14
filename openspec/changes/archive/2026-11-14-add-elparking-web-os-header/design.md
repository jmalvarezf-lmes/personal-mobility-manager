## Context

See `proposal.md` for motivation. The current `ElParkingClient` sends two headers on every ElParking request: `ep-app-name: elparking` and `ep-app-version: <ELPARKING_APP_VERSION>`. ElParking validates the version header against its mobile app releases, which forces us to bump `ELPARKING_APP_VERSION` on every release. Adding `ep-app-os: web` tells ElParking to treat this client as the web channel and skip version validation.

## Goals / Non-Goals

**Goals:**
- Add `ep-app-os: web` to every ElParking HTTP request without changing any other header or request body.
- Keep the change localized to `ElParkingClient` and its tests.
- Preserve `ELPARKING_APP_VERSION` as a configurable seam even though the value no longer gates API acceptance.

**Non-Goals:**
- Removing `ep-app-version` or `ELPARKING_APP_VERSION` configuration.
- Changing `ep-app-name` from `elparking`.
- Changing any other ElParking request body, auth scheme, or endpoint path.
- Adding frontend or API surface changes.

## Decisions

### D1: `ep-app-os: web` is a hardcoded constant
- **Choice**: Add `_EP_APP_OS = "web"` as a module-level constant in `ElParkingClient`, next to the existing `_EP_APP_NAME = "elparking"` constant.
- **Rationale**: The value `"web"` is part of ElParking's API contract, not a deployment preference. Hardcoding it mirrors how `ep-app-name` is treated and avoids adding another env var. If ElParking ever changes the magic value, a one-line code change is acceptable because it is contract-level, not operational.
- **Alternative considered**: Make it configurable via `ELPARKING_APP_OS`. Rejected because there is no evidence operators will need to vary this value per deployment; it would be config clutter for a fixed identity signal.

### D2: Keep `ELPARKING_APP_VERSION` and continue sending `ep-app-version`
- **Choice**: Continue reading `ep-app-version` from `ELPARKING_APP_VERSION` (default `"26.2"`) and sending it on every request.
- **Rationale**: Backward compatibility. If `ep-app-os: web` is ever ignored or misinterpreted by a specific ElParking environment, the existing version header still satisfies the old contract. Removing the env var would be a separate, more breaking change.
- **Alternative considered**: Drop the header entirely once `ep-app-os` is present. Rejected because it creates a sharper behavioral cliff and offers no benefit while the value is easy to keep.

### D3: Single shared header helper
- **Choice**: Extend `ElParkingClient._auth_headers()` to return all three headers; every method (`login`, `logout`, `_authenticated_get`, `create_ticket`) already uses this helper.
- **Rationale**: The existing code already centralizes headers through `_auth_headers()`, so the change is one line in one place. No call sites need to change.

## Risks / Trade-offs

- **[Risk] ElParking does not honor `ep-app-os: web` in all environments** → **Mitigation**: Keep sending `ep-app-version` so the old validation path still works; verify against the live API before considering the change complete.
- **[Risk] Tests assert exact header dicts and will fail until updated** → **Mitigation**: Update `tests/infrastructure/test_elparking_client.py` in the same change.
- **[Trade-off] Hardcoded value vs. env var** → We accept a tiny loss of runtime flexibility in exchange for less configuration surface and clearer intent.

## Migration Plan

1. Deploy the change. All new ElParking requests include `ep-app-os: web`.
2. Monitor ElParking responses for any unexpected 403/401/version-related rejections.
3. If stable, `ELPARKING_APP_VERSION` can be left at its current value indefinitely; future mobile release bumps are no longer required.
4. Rollback: revert the single-line `_auth_headers()` change; no data migration or state change is needed.

## Open Questions

_None — the contract was verified before planning._
