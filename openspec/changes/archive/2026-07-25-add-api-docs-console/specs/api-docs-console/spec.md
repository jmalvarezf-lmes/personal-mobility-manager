## ADDED Requirements

### Requirement: Interactive API documentation console
The system SHALL provide a frontend page that renders an interactive Swagger UI console built from the backend's auto-generated OpenAPI schema, reachable via a link from the main navigation, without requiring authentication to view.

#### Scenario: Anonymous user opens the docs page
- **WHEN** an unauthenticated visitor navigates to the API docs page
- **THEN** the page loads and renders the full list of API operations and schemas from the OpenAPI spec

#### Scenario: Docs link visible from main navigation
- **WHEN** any user (authenticated or not) views the main navigation
- **THEN** a link to the API docs page is visible and does not require login to click

### Requirement: Spec requests resolve through the same-origin API proxy
The system SHALL fetch the OpenAPI spec and issue all "Try it out" requests through the same `/api` same-origin prefix the rest of the frontend already uses, so no cross-origin request is ever made from the docs console.

#### Scenario: Spec is fetched same-origin
- **WHEN** the docs page loads
- **THEN** it fetches the OpenAPI spec from `/api/openapi.json` (proxied to the backend by nginx or the Vite dev server) rather than a cross-origin backend URL

#### Scenario: Try it out request targets the proxied path
- **WHEN** a user executes "Try it out" on any operation in the console
- **THEN** the request is sent to `/api/<operation-path>`, matching the `servers` entry injected into the fetched spec, and not to the bare operation path from the raw OpenAPI document

### Requirement: Session-cookie auth works in the console without extra setup
The system SHALL let an already-logged-in user exercise protected endpoints from the docs console using their existing session cookie, with no manual token entry or Authorize-dialog step, and SHALL return the endpoint's normal 401 response when no valid session cookie is present.

#### Scenario: Logged-in user calls a protected endpoint from the console
- **WHEN** a user who is already logged in (holds a valid session cookie for the app's origin) executes "Try it out" on a protected endpoint
- **THEN** the browser automatically attaches the session cookie to the same-origin request and the endpoint responds as it would for any other authenticated call from the app

#### Scenario: Anonymous user calls a protected endpoint from the console
- **WHEN** a visitor with no session cookie executes "Try it out" on a protected endpoint
- **THEN** the response is the endpoint's normal 401 Unauthorized, identical to calling it without a session from any other client
