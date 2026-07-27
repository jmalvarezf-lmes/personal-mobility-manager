## MODIFIED Requirements

### Requirement: Push endpoint rate-limited
The system SHALL apply two independent rate limits to `POST /vehicles/{token}/location`:
1. The existing per-remote-address limit of `60/minute` (unchanged, shared with the `api-rate-limiting` capability's other endpoints) — guards against abuse from a single source hammering many different vehicle tokens.
2. A new per-vehicle-token limit of `1/minute`, keyed by the `token` path parameter rather than the caller's IP address — added after a 4R review of the `ser-ticket-auto-creation` capability found that, combined with GPS jitter near a SER zone boundary, a single vehicle pushing locations faster than this could retrigger `SerTicketCreationTriggerHandler`'s zone-transition gate (and, in a failure edge case, repeated real ticket-creation attempts against the SER provider) far more often than intended. Capping how often a single vehicle's own location can be updated bounds this independently of GPS noise or the gate's own floor.

Both limits are enforced independently; either being exceeded SHALL result in HTTP 429 for the excess request.

#### Scenario: Excessive push rate rejected (per-remote-address)
- **WHEN** a single remote address sends more than 60 push requests per minute (across any tokens)
- **THEN** the system responds with HTTP 429 for the excess requests

#### Scenario: Excessive push rate rejected (per-vehicle-token)
- **WHEN** a single token is used for more than 1 push request within a minute
- **THEN** the system responds with HTTP 429 for the second and any further request for that same token within that window, regardless of the remote address making the request

#### Scenario: Two different tokens are rate-limited independently
- **WHEN** two different vehicle tokens each push a location within the same one-minute window
- **THEN** neither push is rejected on account of the other — the per-token limit tracks each token's own request count separately
