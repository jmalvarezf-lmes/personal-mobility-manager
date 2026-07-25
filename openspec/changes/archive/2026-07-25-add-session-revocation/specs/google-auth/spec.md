## MODIFIED Requirements

### Requirement: Callback exchanges code, provisions user, and issues JWT cookie
The system SHALL expose `GET /auth/google/callback` that accepts `code` and `state` query parameters from Google. It MUST verify the state signature and max_age (5 minutes). On valid state, it SHALL exchange the code for an ID token via Google's token endpoint, extract `sub`, `email`, and `name` from the userinfo, upsert the user in the `users` table, create a session record, sign a 24h JWT that includes the session's id as a `sid` claim, and set a session cookie. After success it SHALL redirect the browser to `/`.

#### Scenario: Successful callback provisions new user
- **WHEN** Google redirects to `/auth/google/callback` with a valid `code` and `state`
- **THEN** the system exchanges the code for tokens with Google
- **THEN** a new row is inserted in `users` with `google_sub`, `email`, `display_name`
- **THEN** a new row is inserted in `sessions` associated with that user
- **THEN** the response sets `Set-Cookie: session=<JWT>; HttpOnly; Secure; SameSite=Strict; Path=/; Max-Age=86400`
- **THEN** the JWT payload's `sid` claim matches the newly created session's `id`
- **THEN** the response redirects to `/` with HTTP 302

#### Scenario: Successful callback upserts existing user
- **WHEN** Google redirects with a valid code for a `google_sub` already in the database
- **THEN** no duplicate user row is created
- **THEN** the existing user's `email` and `display_name` are updated if changed
- **THEN** a new session row is created for this login
- **THEN** the JWT is issued with the new session's `sid` and the session cookie is set

#### Scenario: Invalid or expired state is rejected
- **WHEN** Google redirects with a `state` that has been tampered with or is older than 5 minutes
- **THEN** the system responds with HTTP 400 and does not issue a session cookie
- **THEN** no session row is created

#### Scenario: Google code exchange fails
- **WHEN** Google returns an error or the code has already been used
- **THEN** the system responds with HTTP 400 and does not issue a session cookie
- **THEN** no session row is created

---

### Requirement: Logout clears the session cookie and revokes the server-side session
The system SHALL expose `POST /auth/logout` that, if the request carries a decodable session cookie, revokes the corresponding server-side session (see `session-management`), clears the `session` cookie by setting it with `Max-Age=0`, and responds with HTTP 204. It SHALL succeed whether or not the user is currently authenticated.

#### Scenario: Logout clears the cookie and revokes the session
- **WHEN** a client sends `POST /auth/logout` with a valid session cookie
- **THEN** the response sets `Set-Cookie: session=; HttpOnly; Secure; SameSite=Strict; Path=/; Max-Age=0`
- **THEN** the response status is HTTP 204
- **THEN** the session referenced by the cookie's `sid` claim is revoked

#### Scenario: Logout is idempotent
- **WHEN** a client sends `POST /auth/logout` without a session cookie
- **THEN** the system still responds with HTTP 204

#### Scenario: A revoked token cannot be reused after logout
- **WHEN** a client sends `POST /auth/logout` with a valid session cookie, and then reuses the same (still cryptographically valid, non-expired) JWT on a subsequent protected request
- **THEN** the subsequent request is rejected with HTTP 401

---

### Requirement: JWT is validated on every protected request, including server-side session state
The system SHALL provide a `get_current_user` FastAPI dependency that reads the `session` cookie, decodes and verifies the JWT (`HS256`, `JWT_SECRET`), and validates the referenced server-side session (not revoked, not expired, owned by the JWT's `sub`) via a `ValidateSession` use case. Expired, missing, or tampered tokens, and tokens whose session is invalid, SHALL result in HTTP 401.

#### Scenario: Valid JWT with a live session grants access
- **WHEN** a protected endpoint is called with a valid session cookie containing a non-expired JWT whose `sid` references a live, non-revoked session owned by the JWT's `sub`
- **THEN** the endpoint proceeds and the user entity is available

#### Scenario: Expired JWT is rejected
- **WHEN** a protected endpoint is called with a session cookie whose JWT `exp` claim is in the past
- **THEN** the system responds with HTTP 401

#### Scenario: Missing cookie is rejected
- **WHEN** a protected endpoint is called with no session cookie
- **THEN** the system responds with HTTP 401

#### Scenario: Valid JWT with a revoked session is rejected
- **WHEN** a protected endpoint is called with a cryptographically valid, non-expired JWT whose `sid` references a session with `revoked_at` set
- **THEN** the system responds with HTTP 401

#### Scenario: JWT missing the sid claim is rejected
- **WHEN** a protected endpoint is called with a cryptographically valid JWT that has no `sid` claim (e.g., issued before this change)
- **THEN** the system responds with HTTP 401
