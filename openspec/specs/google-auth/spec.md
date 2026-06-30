## ADDED Requirements

### Requirement: Backend initiates Google OAuth2 authorization flow
The system SHALL expose `GET /auth/google/login` that redirects the browser to Google's OAuth2 authorization endpoint. The redirect URL MUST include `client_id`, `redirect_uri`, `scope` (`openid email profile`), `response_type=code`, and a signed `state` parameter. The state SHALL be a time-limited token signed with `itsdangerous.URLSafeTimedSerializer` using `JWT_SECRET` as the key.

#### Scenario: Login endpoint redirects to Google
- **WHEN** a client sends `GET /auth/google/login`
- **THEN** the system responds with HTTP 302 to Google's OAuth consent URL
- **THEN** the redirect URL contains `client_id`, `redirect_uri`, `scope=openid+email+profile`, and a non-empty `state` parameter

#### Scenario: State parameter is signed
- **WHEN** the login endpoint generates a state value
- **THEN** the state can be verified by `URLSafeTimedSerializer(JWT_SECRET).loads(state, max_age=300)` without raising
- **THEN** the state contains a random nonce (not a predictable value)

---

### Requirement: Callback exchanges code, provisions user, and issues JWT cookie
The system SHALL expose `GET /auth/google/callback` that accepts `code` and `state` query parameters from Google. It MUST verify the state signature and max_age (5 minutes). On valid state, it SHALL exchange the code for an ID token via Google's token endpoint, extract `sub`, `email`, and `name` from the userinfo, upsert the user in the `users` table, sign a 24h JWT, and set a session cookie. After success it SHALL redirect the browser to `/`.

#### Scenario: Successful callback provisions new user
- **WHEN** Google redirects to `/auth/google/callback` with a valid `code` and `state`
- **THEN** the system exchanges the code for tokens with Google
- **THEN** a new row is inserted in `users` with `google_sub`, `email`, `display_name`
- **THEN** the response sets `Set-Cookie: session=<JWT>; HttpOnly; Secure; SameSite=Strict; Path=/; Max-Age=86400`
- **THEN** the response redirects to `/` with HTTP 302

#### Scenario: Successful callback upserts existing user
- **WHEN** Google redirects with a valid code for a `google_sub` already in the database
- **THEN** no duplicate user row is created
- **THEN** the existing user's `email` and `display_name` are updated if changed
- **THEN** the JWT is issued and the session cookie is set

#### Scenario: Invalid or expired state is rejected
- **WHEN** Google redirects with a `state` that has been tampered with or is older than 5 minutes
- **THEN** the system responds with HTTP 400 and does not issue a session cookie

#### Scenario: Google code exchange fails
- **WHEN** Google returns an error or the code has already been used
- **THEN** the system responds with HTTP 400 and does not issue a session cookie

---

### Requirement: Session introspection endpoint returns current user
The system SHALL expose `GET /auth/me` that reads the `session` cookie, validates the JWT, and returns the current user's `id`, `email`, and `display_name` as JSON. If no valid cookie is present, it SHALL return HTTP 401.

#### Scenario: Authenticated user receives their profile
- **WHEN** a client sends `GET /auth/me` with a valid session cookie
- **THEN** the system responds with HTTP 200 and `{ "id": "<uuid>", "email": "<email>", "display_name": "<name>" }`

#### Scenario: Unauthenticated request is rejected
- **WHEN** a client sends `GET /auth/me` without a session cookie or with an expired/invalid JWT
- **THEN** the system responds with HTTP 401

---

### Requirement: Logout clears the session cookie
The system SHALL expose `POST /auth/logout` that clears the `session` cookie by setting it with `Max-Age=0` and responds with HTTP 204. It SHALL succeed whether or not the user is currently authenticated.

#### Scenario: Logout clears the cookie
- **WHEN** a client sends `POST /auth/logout` with a valid session cookie
- **THEN** the response sets `Set-Cookie: session=; HttpOnly; Secure; SameSite=Strict; Path=/; Max-Age=0`
- **THEN** the response status is HTTP 204

#### Scenario: Logout is idempotent
- **WHEN** a client sends `POST /auth/logout` without a session cookie
- **THEN** the system still responds with HTTP 204

---

### Requirement: JWT is validated on every protected request
The system SHALL provide a `get_current_user` FastAPI dependency that reads the `session` cookie, decodes and verifies the JWT (`HS256`, `JWT_SECRET`), and returns the `User` entity. Expired, missing, or tampered tokens SHALL result in HTTP 401.

#### Scenario: Valid JWT grants access
- **WHEN** a protected endpoint is called with a valid session cookie containing a non-expired JWT
- **THEN** the endpoint proceeds and the user entity is available

#### Scenario: Expired JWT is rejected
- **WHEN** a protected endpoint is called with a session cookie whose JWT `exp` claim is in the past
- **THEN** the system responds with HTTP 401

#### Scenario: Missing cookie is rejected
- **WHEN** a protected endpoint is called with no session cookie
- **THEN** the system responds with HTTP 401
