## 1. Dependencies and Configuration

- [x] 1.1 Add `authlib`, `PyJWT`, and `itsdangerous` to `requirements.txt`. Authlib should be 1.7.2, PyJWT 2.13.0 and itsdangerous 2.2.0.
- [x] 1.2 Add `react-router-dom` and `@types/react-router-dom` to `frontend/package.json` and install
- [x] 1.3 Add `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `JWT_SECRET` to `config.py` with `get_*` accessors (raise `RuntimeError` if missing)
- [x] 1.4 Update `.env.example` with the three new env vars and a note about registering the redirect URI in Google Cloud Console

## 2. Database: Users Table

- [x] 2.1 Create Alembic migration: `create_users` — `id UUID PK`, `google_sub TEXT UNIQUE NOT NULL`, `email TEXT NOT NULL`, `display_name TEXT NOT NULL`, `created_at TIMESTAMP WITH TIME ZONE NOT NULL`

## 3. Database: Vehicle Ownership

- [x] 3.1 Create Alembic migration: `add_user_id_to_vehicles` — truncate `vehicle_locations`, `vehicle_configs`, `vehicles`; add `user_id UUID NOT NULL REFERENCES users(id)` to `vehicles`

## 4. Domain: User Entity and Repository Port

- [x] 4.1 Create `domain/entities/user.py` — frozen dataclass `User` with `id`, `google_sub`, `email`, `display_name`, `created_at`
- [x] 4.2 Create `domain/ports/user_repository.py` — `UserRepository` ABC with `upsert(google_sub, email, display_name) -> User` and `find_by_id(user_id) -> User | None`

## 5. Infrastructure: User Repository

- [x] 5.1 Create `infrastructure/repositories/postgres/user_repo.py` — `PostgresUserRepository` implementing `UserRepository`; `upsert` uses INSERT … ON CONFLICT (google_sub) DO UPDATE; `find_by_id` returns `None` if not found

## 6. Domain: Vehicle Updated with user_id

- [x] 6.1 Add `user_id: UUID` field to `domain/entities/vehicle.py`
- [x] 6.2 Update `infrastructure/repositories/postgres/vehicle_repo.py` to persist and hydrate `user_id`; add `find_by_id(vehicle_id) -> Vehicle | None` method for ownership checks

## 7. Application: Authenticate Google User Use Case

- [x] 7.1 Create `application/use_cases/authenticate_google_user.py` — `AuthenticateGoogleUser` use case: accepts `google_sub`, `email`, `display_name`; calls `user_repo.upsert`; returns `User`

## 8. Application: Register Vehicle Updated

- [x] 8.1 Update `application/use_cases/register_vehicle.py` — add `user_id: UUID` parameter to `execute()`; pass it through to the vehicle repository

## 9. Presentation: Auth Router

- [x] 9.1 Create `presentation/api/deps.py` — `get_current_user(request: Request) -> User` FastAPI dependency: reads `session` cookie, decodes JWT with PyJWT (`HS256`, `JWT_SECRET`), calls `user_repo.find_by_id`, raises `HTTPException(401)` on any failure
- [x] 9.2 Create `presentation/api/csrf.py` — `generate_signed_state() -> str` and `verify_signed_state(state: str) -> None` using `itsdangerous.URLSafeTimedSerializer(JWT_SECRET)` with `max_age=300`
- [x] 9.3 Create `presentation/api/routers/auth.py` — router with prefix `/auth`, tags `["auth"]`:
  - `GET /google/login`: build Google authorization URL via `authlib`, embed signed state, return 302
  - `GET /google/callback`: verify state, exchange code, fetch userinfo, call `AuthenticateGoogleUser`, sign JWT, set `session` cookie (`HttpOnly`, `Secure`, `SameSite=Strict`, `Max-Age=86400`), redirect to `/`
  - `GET /me`: depends on `get_current_user`, returns `{ id, email, display_name }`
  - `POST /logout`: clears `session` cookie with `Max-Age=0`, returns 204
- [x] 9.4 Register `auth_router` in `presentation/api/app.py` lifespan and router includes; wire `user_repo` and `authenticate_google_user` use case into `app.state`

## 10. Presentation: Vehicle Endpoints — Auth and Ownership

- [x] 10.1 Update `presentation/api/routers/vehicles.py` — `POST /vehicles`: add `current_user: User = Depends(get_current_user)`; pass `user_id=current_user.id` to the register use case
- [x] 10.2 Update `presentation/api/routers/vehicles.py` — `GET /{vehicle_id}/location`: add `current_user: User = Depends(get_current_user)`; fetch vehicle from repo; return 403 if `vehicle.user_id != current_user.id`

## 11. Frontend: Auth API Client and Context

- [x] 11.1 Create `frontend/src/api/auth.ts` — `getMe(): Promise<User | null>` (returns `null` on 401) and `logout(): Promise<void>` (calls `POST /api/auth/logout`)
- [x] 11.2 Create `frontend/src/context/AuthContext.tsx` — `AuthContext` providing `user: User | null` and `setUser`; `AuthProvider` calls `getMe()` on mount and stores the result

## 12. Frontend: Routing and Protected Route

- [x] 12.1 Update `frontend/src/App.tsx` — wrap with `AuthProvider`, add `BrowserRouter` and `Routes`: `/` → `LandingPage`, `/map` → `ProtectedRoute` wrapping `MapPage`
- [x] 12.2 Create `frontend/src/components/ProtectedRoute.tsx` — if `user` is `null` (and auth is not loading), `<Navigate to="/" />`; otherwise render children

## 13. Frontend: Navigation Bar

- [x] 13.1 Create `frontend/src/components/Nav.tsx` — renders app title, link to `/map`, and auth control: `<a href="/api/auth/google/login">Login with Google</a>` when unauthenticated; user email + logout button when authenticated

## 14. Frontend: Landing Page

- [x] 14.1 Create `frontend/src/pages/LandingPage.tsx` — renders `<Nav />` and an `<h1>Personal Mobility Manager</h1>` placeholder body; no other content required at this stage

## 15. Frontend: Map Page Navigation

- [x] 15.1 Update `frontend/src/pages/MapPage.tsx` — add `<Nav />` at the top so the navigation bar is visible on the map page

## 16. Tests

- [x] 16.1 Unit test `csrf.py` — verify that `verify_signed_state` raises on tampered state and state older than 5 minutes
- [x] 16.2 Unit test `authenticate_google_user.py` — mock `UserRepository`; verify upsert is called with correct args and the returned `User` is passed through
- [x] 16.3 Unit test `get_current_user` dependency — valid JWT returns user; expired JWT raises 401; missing cookie raises 401
- [x] 16.4 Integration test `POST /vehicles` — unauthenticated request returns 401; authenticated request creates vehicle with correct `user_id`
- [x] 16.5 Integration test `GET /vehicles/{id}/location` — unauthenticated returns 401; owner returns 200; non-owner returns 403
- [x] 16.6 Integration test `GET /auth/me` — valid session returns user JSON; no cookie returns 401
- [x] 16.7 Integration test `POST /auth/logout` — sets expired session cookie; subsequent `GET /auth/me` returns 401
