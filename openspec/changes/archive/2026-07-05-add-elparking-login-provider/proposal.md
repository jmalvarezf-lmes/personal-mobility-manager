## Why

The `ser-ticket-provider` interface (port, registry, credential storage, use cases) was built with no concrete implementation behind it. ElParking is the first real SER ticket provider, and its login API is documented and ready to integrate. Landing login first — with `create_ticket` deferred to a follow-up change — lets users connect their ElParking account through the app now, ahead of ticket creation itself.

## What Changes

- Add `ElParkingSerTicketProvider` implementing `SerTicketProviderPort.login()` against ElParking's `POST /v1/logins`, using a synchronous `httpx.Client`. `create_ticket()` is a deliberate `NotImplementedError` stub — its API spec isn't available yet and it lands in a separate future change.
- Add two domain exceptions: `SerProviderAuthenticationError` (invalid credentials) and `SerProviderApiError` (rate-limited, unexpected/5xx response) — the first real failure contract for `SerTicketProviderPort`, which had none before since nothing called it for real.
- `SerTicketProviderRegistry.build_providers()` now actually registers `ElParkingSerTicketProvider` when enabled via `ENABLED_SER_PROVIDERS` (default: `"elparking"`, mirroring `ENABLED_BRANDS`'s pattern), and fails fast at startup if enabled without `ENCRYPTION_KEY` set — mirroring `BrandRegistry`'s Toyota check.
- Add `POST /ser-ticket-providers/connections` — a protected endpoint accepting `{provider, email, password}`, resolved via a new `SerTicketProviderConnectFactory` (mirrors `VehicleRegisterFactory`) into `SerProviderCredentials`, calling `ConnectSerTicketProvider`. Returns 204 on success, 401 on `SerProviderAuthenticationError`, 502 on `SerProviderApiError`.
- The stored session captures only `access_token` and the device-session `id` from ElParking's login response — nothing else, since all of ElParking's other endpoints derive user context from the token alone.

## Capabilities

### New Capabilities
(none)

### Modified Capabilities
- `ser-ticket-provider`: gains its first concrete provider (ElParking, login only), a real HTTP connection endpoint, a connect-time credential factory, and the interface's first defined authentication/API failure exceptions. No existing requirement's behavior changes — these are additive (new requirements), not modifications to what's already specified.

## Impact

- **New dependency surface**: outbound HTTP calls to ElParking's API from our backend (shared server IP — ElParking's login is IP-rate-limited, so many simultaneous "connect account" attempts could collectively trip their rate limiter; noted as an operational risk, not solved in this change).
- **Backend**: new infrastructure provider (`infrastructure/ser_ticket_providers/elparking/`), two new domain exceptions, `SerTicketProviderRegistry` now does real work, new presentation-layer schema/factory/router, new `ENABLED_SER_PROVIDERS`/reuse of existing `ENCRYPTION_KEY` config.
- **API surface**: new `POST /ser-ticket-providers/connections` endpoint (protected, requires login).
- **No frontend changes** in this proposal — the endpoint exists but no UI calls it yet (out of scope; a follow-up change would add the "connect your ElParking account" UI, likely alongside or after `create_ticket`).
