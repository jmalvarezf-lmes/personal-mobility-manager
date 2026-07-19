### Requirement: Credential-bearing and auth endpoints are rate limited
The system SHALL apply the existing `slowapi` per-remote-address rate limiter, at the same `60/minute` limit already used for `POST /parking/ser-zone` and `POST /vehicles/{token}/location`, to: `POST /vehicles` (vehicle registration), `PUT /vehicles/{vehicle_id}` (vehicle update), `POST /ser-ticket-providers/connections` (SER ticket provider connect), and `GET /auth/google/callback` (OAuth callback). A request exceeding the limit SHALL receive `429 Too Many Requests`, consistent with the project's existing `RateLimitExceeded` handler.

#### Scenario: Excess requests to a newly-covered endpoint are throttled
- **WHEN** a single client (by remote address) sends more than 60 requests within one minute to `POST /vehicles`, `PUT /vehicles/{vehicle_id}`, `POST /ser-ticket-providers/connections`, or `GET /auth/google/callback`
- **THEN** requests beyond the limit receive `429 Too Many Requests`

#### Scenario: Requests within the limit succeed normally
- **WHEN** a single client sends 60 or fewer requests within one minute to any of the newly-covered endpoints
- **THEN** none of those requests are rejected for rate-limit reasons
