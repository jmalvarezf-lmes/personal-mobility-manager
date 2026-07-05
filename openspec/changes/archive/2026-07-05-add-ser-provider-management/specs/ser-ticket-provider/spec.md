## ADDED Requirements

### Requirement: SerTicketProviderPort defines a logout method
The system SHALL extend `SerTicketProviderPort` with an abstract `logout(self, session: SerProviderSession) -> None` method, invalidating the provider-side session. Implementations that raise for any failure SHALL raise `SerProviderApiError`, consistent with `login`'s existing failure vocabulary.

#### Scenario: Provider implements logout
- **WHEN** a concrete `SerTicketProviderPort` implementation is asked to log out a valid session
- **THEN** it invalidates that session on the provider's side and returns without error

#### Scenario: Logout failure raises SerProviderApiError
- **WHEN** a provider's logout call fails (network error, unexpected response)
- **THEN** it raises `SerProviderApiError`, not a generic or provider-specific exception

---

### Requirement: ElParkingSerTicketProvider implements logout
`ElParkingSerTicketProvider.logout` SHALL call ElParking's `DELETE /v1/logins/{access_token}` (using the `access_token` from `session.data`), including an `Authorization: Bearer {access_token}` header.

#### Scenario: Successful logout calls ElParking's revoke endpoint
- **WHEN** `logout` is called with a valid session
- **THEN** a `DELETE` request is sent to `{base_url}/v1/logins/{access_token}`

#### Scenario: Logout failure is wrapped
- **WHEN** ElParking's logout endpoint is unreachable or returns an unexpected status
- **THEN** `SerProviderApiError` is raised and no raw `httpx` exception propagates

---

### Requirement: UserSerProviderConfigRepository supports deletion and listing
The system SHALL extend `UserSerProviderConfigRepository` with:
- `delete(user_id: UUID, provider: str) -> None` — removes the stored session for `(user_id, provider)`, if present. SHALL NOT raise if no such row exists (idempotent).
- `list_connected_providers(user_id: UUID) -> list[str]` — returns the provider names for which `user_id` has a stored session.

#### Scenario: Delete removes an existing session
- **WHEN** `delete` is called for a `(user_id, provider)` pair with a stored session
- **THEN** a subsequent `find` for the same pair returns `None`

#### Scenario: Delete is idempotent
- **WHEN** `delete` is called for a `(user_id, provider)` pair with no stored session
- **THEN** it completes without raising

#### Scenario: list_connected_providers reflects stored sessions
- **WHEN** a user has stored sessions for `"elparking"` and no other provider
- **THEN** `list_connected_providers` returns `["elparking"]`

#### Scenario: list_connected_providers returns empty for a user with no connections
- **WHEN** a user has no stored SER provider sessions
- **THEN** `list_connected_providers` returns an empty list

---

### Requirement: DisconnectSerTicketProvider use case removes a connection with best-effort logout
The system SHALL define `DisconnectSerTicketProvider` with `execute(user_id: UUID, provider: str) -> bool`, returning whether the provider-side logout succeeded. It SHALL:
- Return `True` immediately if no session exists for `(user_id, provider)` (idempotent success).
- Attempt `provider.logout(session)` via the registered provider instance if one is available; treat a missing/unregistered provider instance as a logout failure, not an error.
- Catch `SerProviderApiError` from `logout` without propagating it.
- Always call `UserSerProviderConfigRepository.delete(user_id, provider)`, regardless of whether logout succeeded.

#### Scenario: Full disconnect when logout succeeds
- **WHEN** `execute` is called for a connected user and the provider's logout succeeds
- **THEN** it returns `True`
- **THEN** the local session is deleted

#### Scenario: Disconnect completes even when logout fails
- **WHEN** `execute` is called for a connected user and the provider's logout raises `SerProviderApiError`
- **THEN** it returns `False`
- **THEN** the local session is still deleted

#### Scenario: Disconnect completes when the provider is unregistered
- **WHEN** `execute` is called for a provider that is not currently registered (e.g. disabled via configuration since the user connected)
- **THEN** it returns `False`
- **THEN** the local session is still deleted

#### Scenario: Disconnecting an already-disconnected provider is a no-op success
- **WHEN** `execute` is called for a `(user_id, provider)` pair with no stored session
- **THEN** it returns `True` without attempting to contact any provider

---

### Requirement: ListSerTicketProviderConnections use case reports connected providers
The system SHALL define a use case with `execute(user_id: UUID) -> list[str]`, returning `UserSerProviderConfigRepository.list_connected_providers(user_id)`.

#### Scenario: Reports currently connected providers
- **WHEN** `execute` is called for a user with a stored ElParking session
- **THEN** it returns `["elparking"]`

---

### Requirement: Authenticated user can list their SER provider connections
The system SHALL expose `GET /ser-ticket-providers/connections`, requiring an authenticated session, returning `{"providers": [<provider names>]}` for the current user.

#### Scenario: Returns connected providers
- **WHEN** an authenticated user with a connected ElParking account calls `GET /ser-ticket-providers/connections`
- **THEN** the response is `200 OK` with `{"providers": ["elparking"]}`

#### Scenario: Returns an empty list when nothing is connected
- **WHEN** an authenticated user with no connections calls `GET /ser-ticket-providers/connections`
- **THEN** the response is `200 OK` with `{"providers": []}`

#### Scenario: Anonymous request is rejected
- **WHEN** a request without a valid session cookie is sent to `GET /ser-ticket-providers/connections`
- **THEN** the response is `401 Unauthorized`

---

### Requirement: Authenticated user can disconnect a SER provider connection
The system SHALL expose `DELETE /ser-ticket-providers/connections/{provider}`, requiring an authenticated session, calling `DisconnectSerTicketProvider.execute` for the current user and the path's `provider`. It SHALL respond `200 OK` with `{"logout_succeeded": <bool>}` — never `204`, since the body must carry the soft-failure signal.

#### Scenario: Successful disconnect with confirmed logout
- **WHEN** an authenticated user disconnects a provider and the provider-side logout succeeds
- **THEN** the response is `200 OK` with `{"logout_succeeded": true}`
- **THEN** a subsequent `GET /ser-ticket-providers/connections` no longer lists that provider

#### Scenario: Disconnect succeeds locally even if logout could not be confirmed
- **WHEN** an authenticated user disconnects a provider and the provider-side logout fails
- **THEN** the response is `200 OK` with `{"logout_succeeded": false}`
- **THEN** a subsequent `GET /ser-ticket-providers/connections` no longer lists that provider

#### Scenario: Anonymous request is rejected
- **WHEN** a request without a valid session cookie is sent to `DELETE /ser-ticket-providers/connections/{provider}`
- **THEN** the response is `401 Unauthorized` and no provider is contacted

---

### Requirement: SER Providers page lets a user connect, view, and disconnect provider accounts
The system SHALL provide a frontend "SER Providers" page, reachable only via a protected route, listing known SER ticket providers (ElParking today) with their connection status, a way to connect (submitting credentials via a modal), and a way to disconnect an existing connection. If a disconnect's `logout_succeeded` is `false`, the page SHALL inform the user without treating the disconnect as failed.

#### Scenario: Logged-out user cannot reach the SER Providers page
- **WHEN** an unauthenticated visitor navigates to the SER Providers route
- **THEN** they are redirected away, consistent with other protected routes

#### Scenario: Connecting a provider updates its displayed status
- **WHEN** a logged-in user submits valid credentials for a not-yet-connected provider
- **THEN** the page reflects that provider as connected without requiring a manual refresh

#### Scenario: Disconnecting shows a soft warning on unconfirmed logout
- **WHEN** a logged-in user disconnects a provider and the response indicates `logout_succeeded: false`
- **THEN** the page shows the provider as disconnected
- **THEN** the page also displays a non-blocking message noting the provider-side logout could not be confirmed

---

### Requirement: SER Providers page shows a provider icon
Each provider row on the SER Providers page SHALL display an icon sourced from a locally-hosted static asset (`/provider-logos/{provider}.webp`), never hotlinked from a third-party URL. If the asset is unavailable, the row SHALL render without the icon rather than showing a broken-image placeholder — this is a purely presentational concern, unrelated to the API, domain model, or stored data.

#### Scenario: Icon renders when the asset exists
- **WHEN** a provider row is displayed and its logo asset exists at the expected local path
- **THEN** the icon is shown alongside the provider's name

#### Scenario: Missing icon degrades gracefully
- **WHEN** a provider row is displayed and its logo asset does not exist or fails to load
- **THEN** the row still renders fully (name, status, action button), without a broken-image indicator

---

### Requirement: Logged-in navigation includes a SER Providers entry
The system SHALL add a "SER Providers" link to the existing account dropdown menu, alongside My Vehicles, Preferences, and Logout.

#### Scenario: Logged-in user sees the SER Providers entry
- **WHEN** an authenticated user opens the account dropdown
- **THEN** it includes a link to the SER Providers page, alongside the existing entries
