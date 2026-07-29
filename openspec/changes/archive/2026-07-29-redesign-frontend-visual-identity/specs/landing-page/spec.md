## MODIFIED Requirements

### Requirement: Landing page is the app entry point at /
The system SHALL serve a landing page at `/` that explains the product: a hero section with a headline and supporting copy plus a login call to action, and a feature section highlighting the product's three core capabilities (vehicle tracking, SER zone ticket automation, notifications), alongside the navigation menu. The page is accessible to unauthenticated and authenticated users alike. It SHALL NOT redirect either group away.

#### Scenario: Unauthenticated user sees landing page with hero, features, and login button
- **WHEN** an unauthenticated user navigates to `/`
- **THEN** a hero section renders with a headline, supporting copy, and a "Login with Google" link pointing to `/api/auth/google/login`
- **THEN** a feature section renders three highlights covering vehicle tracking, SER zone ticket automation, and notifications
- **THEN** the navigation menu contains a link to the map

#### Scenario: Authenticated user sees landing page with hero, features, and user info
- **WHEN** an authenticated user navigates to `/`
- **THEN** the same hero and feature sections render as for an unauthenticated user
- **THEN** the navigation bar displays the user's email
- **THEN** the "Login with Google" button is replaced by a logout control
- **THEN** the navigation menu contains a link to the map

### Requirement: Navigation bar is shared across pages
The system SHALL render a persistent navigation bar on all pages (`/`, `/map`, `/my-vehicles`, `/preferences`, `/ser-providers`, `/notification-channels`) that contains: the app title/logo rendered as a link to `/`, a link to the map, a language selector, and an auth control (login button when unauthenticated, user email + logout when authenticated). All nav labels SHALL be localised via the active i18n locale.

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

#### Scenario: Nav title links to home
- **WHEN** a user on any page clicks the nav title/logo
- **THEN** the app navigates to `/`
