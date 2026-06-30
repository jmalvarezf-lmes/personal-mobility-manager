## Why

The app currently has no authentication — all pages are anonymous and vehicles have no owner. Introducing Google OAuth lets users identify themselves, own their vehicles, and access user-scoped data securely, while keeping public endpoints (parking zones, SER queries) open.

## What Changes

- Add a backend-driven Google OAuth2 login flow (`/auth/google/login` → Google → `/auth/google/callback`) that auto-provisions users on first login and issues a short-lived (24h) JWT stored in an `HttpOnly; Secure; SameSite=Strict` cookie.
- Add a presentation landing page (`/`) with app branding, navigation, and a "Login with Google" button; the current map moves to `/map`.
- Add `react-router-dom` routing to the frontend with a protected `/map` route.
- Add a persistent `users` table. Link `vehicles` to `users` via a `user_id NOT NULL` FK (vehicles table is dev-only, safe migration).
- Protect vehicle registration (`POST /vehicles`) and location query (`GET /vehicles/{id}/location`) behind JWT auth; the device push endpoint (`POST /vehicles/{token}/location`) remains open.
- Expose `GET /auth/me` so the frontend can check session state and display the logged-in user's email.

## Capabilities

### New Capabilities

- `google-auth`: Backend-driven OAuth2 flow with Google, user auto-provisioning, JWT cookie issuance, logout, and session introspection (`/auth/me`).
- `user-identity`: `users` table, `User` domain entity, and `UserRepository` with upsert-by-google-sub.
- `landing-page`: React landing page at `/` with app title, navigation menu, and "Login with Google" link; nav bar showing user email when authenticated.

### Modified Capabilities

- `vehicle-registry`: `POST /vehicles` now requires JWT auth; `user_id` (from token) is stored on the vehicle at registration. `GET /vehicles/{id}/location` now requires JWT auth and enforces owner-only access.

## Impact

**Backend**
- New tables: `users`, migration adds `user_id NOT NULL` to `vehicles`
- New libraries: `authlib` (OAuth2 client), `PyJWT` (JWT sign/verify)
- New modules: `domain/entities/user.py`, `infrastructure/repositories/postgres/user_repo.py`, `presentation/api/routers/auth.py`, `presentation/api/deps.py`
- Config: `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `JWT_SECRET` env vars
- CORS: callback URL must be registered in Google Cloud Console

**Frontend**
- New dependency: `react-router-dom`
- New pages: `LandingPage`; `MapPage` moves to `/map`
- New components: `Nav`, `ProtectedRoute`
- New context: `AuthContext` (user state from `GET /auth/me`)
- New API client: `auth.ts`
