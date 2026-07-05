## ADDED Requirements

### Requirement: SerProviderAuthenticationError and SerProviderApiError define the port's failure contract
The system SHALL define `SerProviderAuthenticationError` (raised when a provider rejects credentials as invalid) and `SerProviderApiError` (raised for any other provider-side failure: network errors, rate limiting, unexpected/malformed responses) as domain exceptions, following the existing `class XError(Exception): pass` convention.

#### Scenario: Authentication failure is distinguishable from other failures
- **WHEN** a `SerTicketProviderPort.login` implementation cannot authenticate due to invalid credentials
- **THEN** it raises `SerProviderAuthenticationError`, not `SerProviderApiError` or a generic exception

#### Scenario: Non-authentication failures are distinguishable
- **WHEN** a `SerTicketProviderPort.login` implementation fails for any reason other than credential rejection (network failure, unexpected response, rate limiting)
- **THEN** it raises `SerProviderApiError`

---

### Requirement: ElParkingSerTicketProvider implements login against the ElParking API
The system SHALL provide `ElParkingSerTicketProvider`, an implementation of `SerTicketProviderPort`, whose `login` method calls ElParking's `POST /v1/logins` endpoint with `email`/`password` (and `uid`/`model` if present) from `credentials.data`, using header `ep-app-name: elparking` (hardcoded) and header `ep-app-version` sourced from the `ELPARKING_APP_VERSION` environment variable (default: `"26.2"`), since the app version is expected to evolve over time. On success, it SHALL return a `SerProviderSession` whose `data` contains exactly `access_token` (str) and `device_session_id` (int, from the response's `id` field) — no other fields from the response.

#### Scenario: ep-app-version defaults to 26.2
- **WHEN** `login` is called and `ELPARKING_APP_VERSION` is not set
- **THEN** the request to ElParking includes header `ep-app-version: 26.2`

#### Scenario: ep-app-version is configurable
- **WHEN** `ELPARKING_APP_VERSION` is set to a different value
- **THEN** the request to ElParking includes that value as `ep-app-version`, not the default

#### Scenario: Successful login returns a minimal session
- **WHEN** `login` is called with valid ElParking credentials and the API returns a 2xx response with `access_token` and `id`
- **THEN** the returned `SerProviderSession.data` contains exactly `{"access_token": <value>, "device_session_id": <value>}`

#### Scenario: Invalid credentials raise SerProviderAuthenticationError
- **WHEN** `login` is called with credentials ElParking rejects as invalid
- **THEN** `SerProviderAuthenticationError` is raised and no session is returned

#### Scenario: Unexpected API failure raises SerProviderApiError
- **WHEN** the ElParking API is unreachable, returns a 5xx or 429 response, or an unexpected response shape
- **THEN** `SerProviderApiError` is raised, and no raw `httpx` exception propagates out of the provider

---

### Requirement: ElParkingSerTicketProvider.create_ticket is an explicit not-yet-implemented stub
The system SHALL have `ElParkingSerTicketProvider.create_ticket` raise `NotImplementedError` with a message indicating ticket creation is not yet implemented for this provider.

#### Scenario: create_ticket is called before it exists
- **WHEN** `ElParkingSerTicketProvider.create_ticket` is called
- **THEN** it raises `NotImplementedError`, and no HTTP call to ElParking is made

---

### Requirement: SerTicketProviderRegistry registers ElParking when enabled
`SerTicketProviderRegistry.build_providers()` SHALL include `ElParkingSerTicketProvider` under the key `"elparking"` when `"elparking"` appears in the comma-separated `ENABLED_SER_PROVIDERS` environment variable (default: `"elparking"`, i.e. enabled unless explicitly overridden). If `"elparking"` is enabled but `ENCRYPTION_KEY` is not set, the system SHALL raise `RuntimeError` at startup — this SHALL NOT be deferred to the first connection attempt.

#### Scenario: ElParking is registered by default
- **WHEN** `ENABLED_SER_PROVIDERS` is not set and the registry is built with `ENCRYPTION_KEY` present
- **THEN** the returned mapping contains `"elparking"` bound to an `ElParkingSerTicketProvider` instance

#### Scenario: ElParking can be disabled
- **WHEN** `ENABLED_SER_PROVIDERS` is set to a value that does not include `"elparking"` (e.g. `""`)
- **THEN** the returned mapping does not contain `"elparking"`

#### Scenario: Missing encryption key fails fast at startup
- **WHEN** `"elparking"` is enabled via `ENABLED_SER_PROVIDERS` but `ENCRYPTION_KEY` is not set
- **THEN** building the registry raises `RuntimeError` immediately, before any user can attempt to connect an account

---

### Requirement: SerTicketProviderConnectFactory builds provider-specific credentials
The system SHALL provide `SerTicketProviderConnectFactory` in the presentation layer, which builds a `SerProviderCredentials` from a validated connect-request body and the current user's id. For ElParking, the resulting `credentials.data` SHALL include `email`, `password`, `uid` (set to `str(user_id)`), and `model` (a fixed string identifying this backend as a server integration).

#### Scenario: Factory injects a stable, non-random uid
- **WHEN** the factory builds `SerProviderCredentials` for an ElParking connect request from user `user_id`
- **THEN** `credentials.data["uid"]` equals `str(user_id)`, not a randomly generated value

---

### Requirement: Authenticated user can create a SER provider connection over HTTP
The system SHALL expose `POST /ser-ticket-providers/connections`, requiring an authenticated session, accepting a discriminated request body (`provider` field selects the shape, e.g. `ConnectElParkingRequest` for `provider: "elparking"` with `email` and `password`). On success, it calls `ConnectSerTicketProvider.execute` for the current user and returns `204 No Content`. `SerProviderAuthenticationError` SHALL map to `401 Unauthorized`; `SerProviderApiError` SHALL map to `502 Bad Gateway`; `SerTicketProviderNotFoundError` (unknown/disabled provider) SHALL map to `404 Not Found`.

#### Scenario: Successful connection
- **WHEN** an authenticated user submits valid ElParking credentials to `POST /ser-ticket-providers/connections`
- **THEN** the response is `204 No Content`
- **THEN** a session is persisted for that user and `"elparking"`

#### Scenario: Invalid credentials surface as 401
- **WHEN** an authenticated user submits credentials ElParking rejects
- **THEN** the response is `401 Unauthorized`, and no session is persisted

#### Scenario: Provider-side failure surfaces as 502
- **WHEN** the ElParking API is unreachable or returns an unexpected failure during a connection attempt
- **THEN** the response is `502 Bad Gateway`, and no session is persisted

#### Scenario: Anonymous request is rejected
- **WHEN** a request without a valid session cookie is sent to `POST /ser-ticket-providers/connections`
- **THEN** the response is `401 Unauthorized` and no provider is contacted
