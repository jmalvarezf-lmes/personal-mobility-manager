## MODIFIED Requirements

### Requirement: ElParkingSerTicketProvider implements login against the ElParking API
The system SHALL provide `ElParkingSerTicketProvider`, an implementation of `SerTicketProviderPort`, whose `login` method calls ElParking's `POST /v1/logins` endpoint with `email`/`password` (and `uid`/`model` if present) from `credentials.data`, using headers `ep-app-name: elparking` (hardcoded), `ep-app-version` sourced from the `ELPARKING_APP_VERSION` environment variable (default: `"26.2"`), and `ep-app-os: web` (hardcoded). On success, it SHALL return a `SerProviderSession` whose `data` contains exactly `access_token` (str) and `device_session_id` (int, from the response's `id` field) — no other fields from the response.

#### Scenario: ep-app-os is web on login
- **WHEN** `login` is called
- **THEN** the request to ElParking includes header `ep-app-os: web`

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

### Requirement: ElParkingClient centralizes ElParking HTTP calls with correct authentication
The system SHALL provide `ElParkingClient`, an infrastructure helper wrapping every ElParking HTTP call (`login`, `logout`, list the user's vehicles, list SER towns, list a town's zones, fetch pricing/checksum steps, create a ticket). Every call, including `login`, SHALL include the headers `ep-app-name: elparking`, `ep-app-version` sourced from `ELPARKING_APP_VERSION`, and `ep-app-os: web`. Every authenticated call (all except `login`) SHALL authenticate with HTTP Basic auth using a blank username and the session's `access_token` as the password, and SHALL include the same `ep-app-name`/`ep-app-version`/`ep-app-os` headers used by `login`.

#### Scenario: Authenticated calls use HTTP Basic auth, not Bearer
- **WHEN** `ElParkingClient` makes any authenticated call other than `login`
- **THEN** the request is sent with HTTP Basic auth (blank username, `access_token` as password), and no `Authorization: Bearer` header is sent

#### Scenario: Authenticated calls include the required app headers
- **WHEN** `ElParkingClient` makes any authenticated call
- **THEN** the request includes `ep-app-name`, `ep-app-version`, and `ep-app-os: web` headers with the same values `login` sends

#### Scenario: Login includes the required app headers
- **WHEN** `ElParkingClient.login` is called
- **THEN** the request includes `ep-app-name`, `ep-app-version`, and `ep-app-os: web` headers
