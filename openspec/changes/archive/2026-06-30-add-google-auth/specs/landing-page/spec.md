## ADDED Requirements

### Requirement: Landing page is the app entry point at /
The system SHALL serve a landing page at `/` that displays the application title "Personal Mobility Manager" and a navigation menu. The page is accessible to unauthenticated users. It SHALL NOT redirect unauthenticated users away.

#### Scenario: Unauthenticated user sees landing page with login button
- **WHEN** an unauthenticated user navigates to `/`
- **THEN** the page renders with the title "Personal Mobility Manager"
- **THEN** the page renders a "Login with Google" link pointing to `/api/auth/google/login`
- **THEN** the navigation menu contains a link to the map

#### Scenario: Authenticated user sees landing page with user info
- **WHEN** an authenticated user navigates to `/`
- **THEN** the page renders with the title "Personal Mobility Manager"
- **THEN** the navigation bar displays the user's email
- **THEN** the "Login with Google" button is replaced by a logout control
- **THEN** the navigation menu contains a link to the map

---

### Requirement: Navigation bar is shared across pages
The system SHALL render a persistent navigation bar on all pages (`/` and `/map`) that contains: the app title/logo, a link to the map, and an auth control (login button when unauthenticated, user email + logout when authenticated).

#### Scenario: Nav shows login when no session
- **WHEN** the app loads and `GET /auth/me` returns HTTP 401
- **THEN** the nav bar shows a "Login with Google" link

#### Scenario: Nav shows user email when authenticated
- **WHEN** the app loads and `GET /auth/me` returns HTTP 200 with user data
- **THEN** the nav bar shows the user's email
- **THEN** the nav bar shows a logout button that calls `POST /auth/logout` and clears client state

---

### Requirement: /map is a protected route
The system SHALL protect the `/map` route so that unauthenticated users are redirected to `/`. Authenticated users can access the map without restriction.

#### Scenario: Unauthenticated access to /map redirects to /
- **WHEN** an unauthenticated user navigates to `/map`
- **THEN** the app redirects to `/`

#### Scenario: Authenticated user accesses /map normally
- **WHEN** an authenticated user navigates to `/map`
- **THEN** the map page renders without redirection

---

### Requirement: Auth state is loaded once at app startup
The system SHALL call `GET /auth/me` once when the React app mounts to determine the current authentication state. The result SHALL be stored in a React context (`AuthContext`) accessible to all components.

#### Scenario: Auth state initialises from /auth/me on mount
- **WHEN** the React app first renders
- **THEN** `GET /auth/me` is called exactly once
- **THEN** if HTTP 200, the returned user object is stored in `AuthContext`
- **THEN** if HTTP 401, `AuthContext` user is `null`

#### Scenario: Post-login redirect resolves auth state
- **WHEN** the browser is redirected to `/` after a successful Google login
- **THEN** `GET /auth/me` is called on mount and returns the newly provisioned user
- **THEN** the nav bar displays the user's email without a page reload
