## MODIFIED Requirements

### Requirement: Navigation bar is shared across pages
The system SHALL render a persistent navigation bar on all pages (`/`, `/map`, `/my-vehicles`) that contains: the app title/logo, a link to the map, a language selector, and an auth control (login button when unauthenticated, user email + logout when authenticated). All nav labels SHALL be localised via the active i18n locale.

#### Scenario: Nav shows login when no session
- **WHEN** the app loads and `GET /auth/me` returns HTTP 401
- **THEN** the nav bar shows a localised "Login with Google" link (e.g. "Iniciar sesión con Google" in Spanish)

#### Scenario: Nav shows user email when authenticated
- **WHEN** the app loads and `GET /auth/me` returns HTTP 200 with user data
- **THEN** the nav bar shows the user's email
- **THEN** the nav bar shows a localised logout button that calls `POST /auth/logout` and clears client state

#### Scenario: Nav shows language selector
- **WHEN** the app loads in any state
- **THEN** the nav bar displays a language selector with the current locale pre-selected
