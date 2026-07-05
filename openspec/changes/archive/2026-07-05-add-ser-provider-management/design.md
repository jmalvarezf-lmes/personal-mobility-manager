## Context

`add-elparking-login-provider` shipped `POST /ser-ticket-providers/connections` (connect only) with no way to check status or disconnect. `UserSerProviderConfigRepository` only supports `save`/`find`; there's no `delete`. `SerTicketProviderPort` only has `login`/`create_ticket` (the latter a `NotImplementedError` stub). This change closes the loop: proper disconnect (with best-effort provider-side logout), a status-check endpoint, and the frontend page to use both.

`PostgresUserSerProviderConfigRepository.save` already uses `ON CONFLICT DO UPDATE`, so reconnecting (submitting new credentials for an already-connected provider) works via the existing `POST` endpoint with no changes needed there.

## Goals / Non-Goals

**Goals:**
- `SerTicketProviderPort` gains `logout(session) -> None`; `ElParkingSerTicketProvider.logout()` implements it against ElParking's `DELETE /v1/logins/{access_token}`.
- Disconnecting a provider always removes the local session record, and attempts a best-effort server-side logout that never blocks the deletion if it fails.
- `GET /ser-ticket-providers/connections` returns which providers the current user has connected, in one request (not one request per provider).
- A "SER Providers" page lets a user connect, see status, and disconnect, mirroring the existing My Vehicles card/modal pattern.

**Non-Goals:**
- `create_ticket` — still out of scope, still a stub, unrelated to this change.
- Any second concrete provider — the frontend hardcodes `["elparking"]` as the known-provider list, same convention `AddVehicleModal` already uses for brand options.
- Automatic reconnection or credential refresh flows beyond what the existing upsert-based `POST` already provides.

## Decisions

### 1. `logout` is a required (abstract) port method
Mirrors `login`/`create_ticket` — both abstract on `SerTicketProviderPort`. A future provider that genuinely has no server-side session to invalidate can implement it as a no-op; the interface stays uniform rather than making logout optional/defaulted, since "should I clean up server-side" is a real per-provider decision that shouldn't silently default to "do nothing."

`ElParkingSerTicketProvider.logout(session)` extracts `access_token` from `session.data` and calls `DELETE {base_url}/v1/logins/{access_token}`, including `Authorization: Bearer {access_token}` — **an assumption**, since the docs available only show the path shape, not whether the header is also required. Isolated the same way the previous change isolated its invalid-credentials status-code guess: a single, clearly commented point of adjustment if real-API testing shows otherwise. Failures (network error, unexpected status, `httpx.HTTPError`) raise `SerProviderApiError`, consistent with `login`'s existing failure vocabulary — no new exception type needed since this is the same "provider-side thing went wrong" bucket.

### 2. Disconnect is best-effort on logout, unconditional on local deletion
```
DisconnectSerTicketProvider.execute(user_id, provider) -> bool (logout_succeeded):
    session = config_repo.find(user_id, provider)
    if session is None:
        return True   # idempotent — "already disconnected" is success, not an error

    logout_succeeded = True
    provider_instance = providers.get(provider)
    if provider_instance is None:
        logout_succeeded = False        # can't attempt logout — provider disabled/unregistered
    else:
        try:
            provider_instance.logout(session)
        except SerProviderApiError:
            logout_succeeded = False    # soft-fail — never raises further

    config_repo.delete(user_id, provider)   # always runs
    return logout_succeeded
```
Rationale: a user disconnecting should never be blocked by the provider being temporarily unreachable, or by it having been disabled server-side since they connected — local cleanup must always succeed. The boolean return lets the router/frontend distinguish "fully disconnected" from "disconnected locally, but we couldn't confirm the provider-side session was revoked," per the user's explicit requirement to inform without failing.

### 3. `DELETE /ser-ticket-providers/connections/{provider}` returns 200, not 204
A `204 No Content` can't carry the `logout_succeeded` signal the frontend needs to decide whether to show a soft warning. Response body: `{"logout_succeeded": bool}`.

### 4. `GET /ser-ticket-providers/connections` — collection endpoint, one new repo method
Returns `{"providers": ["elparking"]}` (the list of provider names the current user has a stored session for). Requires `UserSerProviderConfigRepository.list_connected_providers(user_id) -> list[str]` — a new method, but a trivial one (`SELECT provider FROM user_ser_provider_configs WHERE user_id = ...`). Chosen over a per-provider `GET .../connections/{provider}` (which would reuse the existing `find` method with zero new repo surface) because the frontend page renders a list of provider rows and should do so from a single network call, not N calls scaling with the number of known providers. The added repo method is small enough that this trade favors the simpler frontend integration.

### 5. Frontend: hardcoded known-provider list, cross-referenced against connection status
The "SER Providers" page renders one row per frontend-hardcoded provider name (today: just `"elparking"`), each looked up against the `GET` response to show connected/not-connected. This mirrors `AddVehicleModal`'s existing convention of hardcoding brand options client-side rather than fetching them from an API — consistent with how this codebase already handles small, slow-changing enumerations. Connecting opens a modal (email/password form) mirroring `AddVehicleModal`'s structure; disconnecting is a button on the row, with a confirmation step (mirroring `MyVehiclesPage`'s delete-confirmation pattern) and a non-blocking warning banner if the response's `logout_succeeded` is `false`.

### 6. Nav: fourth dropdown item, no restructuring
"SER Providers" added to the existing account dropdown (My Vehicles / Preferences / SER Providers / Logout) — the dropdown already scales to this without any layout change.

### 7. Provider icon: locally-hosted static asset, not hotlinked, graceful degradation
Each row on the SER Providers page shows a provider icon, sourced from `frontend/public/provider-logos/{provider}.webp`. This is a locally-hosted static asset supplied by the project owner (not fetched from a third-party URL) — app icons are typically copyrighted by their owner, so hotlinking one from an external CDN (e.g. a Play Store asset URL) would be both fragile (URL could change or break) and legally questionable. The `<img>` uses `onError` to hide itself if the asset is missing, so a not-yet-supplied icon degrades to "no icon" rather than a broken-image placeholder — the page remains fully functional either way. This is a purely presentational addition: no API, domain entity, or stored data changes; the provider identifier used to build the image path is the same string already used everywhere else in this capability (`"elparking"`).

## Risks / Trade-offs

- **[Risk] The `Authorization: Bearer` assumption for ElParking's logout endpoint may be wrong.** → Mitigation: isolated to a single, clearly commented point in `ElParkingSerTicketProvider.logout()`; manual verification against the live API (same pattern as the previous change) should confirm or correct it before this is relied on in production.
- **[Risk] Adding `logout` to `SerTicketProviderPort` is a breaking change to the interface.** → Mitigation: only one concrete implementer exists (`ElParkingSerTicketProvider`), so the blast radius is exactly one file; this is the cheapest point in the project's life to make this change.
- **[Trade-off] `list_connected_providers` adds a small amount of new repository surface for a query that could theoretically be done client-side by calling `find` N times.** → Accepted per Decision 4 — favors a simpler, single-request frontend over avoiding one new repo method.

## Migration Plan

1. Deploy backend changes — additive only, no existing endpoint's behavior changes.
2. No database migration needed — `user_ser_provider_configs` already exists; `delete`/`list_connected_providers` are query-level additions, not schema changes.
3. Deploy frontend changes.
4. Rollback: revert the code change; no data migration to undo.

## Open Questions

None outstanding.
