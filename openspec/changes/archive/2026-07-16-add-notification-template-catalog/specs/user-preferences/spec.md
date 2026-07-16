## MODIFIED Requirements

### Requirement: Preferences page is visible only when logged in
The system SHALL provide a frontend "Preferences" page, reachable only via a protected route, that lets the user view and edit `default_ticket_duration_minutes`, `auto_create_ticket`, `preferred_notification_channel`, and `notification_language`. The `preferred_notification_channel` control SHALL only offer choices among the channels the user currently has connected (per `GET /notifications/channels`), plus an option to clear the preference. The `notification_language` control SHALL offer the system's supported languages, sourced from `GET /notifications/languages` rather than a hardcoded frontend list, so the offered options and the backend's `PUT /preferences` validation cannot drift apart.

#### Scenario: Logged-out user cannot reach the preferences page
- **WHEN** an unauthenticated visitor navigates to the preferences route
- **THEN** they are redirected away (consistent with other protected routes such as My Vehicles)

#### Scenario: Logged-in user edits and saves preferences
- **WHEN** an authenticated user changes the duration and the auto-create toggle on the preferences page and saves
- **THEN** the page calls `PUT /preferences` with the new values

#### Scenario: Logged-in user picks a preferred notification channel
- **WHEN** an authenticated user with one or more connected notification channels selects one as preferred and saves
- **THEN** the page calls `PUT /preferences` with that channel as `preferred_notification_channel`
- **THEN** the page reflects the saved value on success

#### Scenario: User with no connected channels sees no selectable options
- **WHEN** an authenticated user with no connected notification channels views the preferences page
- **THEN** the preferred-channel control shows no selectable channel options

#### Scenario: Logged-in user picks a notification language
- **WHEN** an authenticated user selects a notification language and saves
- **THEN** the page calls `PUT /preferences` with that value as `notification_language`
- **THEN** the page reflects the saved value on success

#### Scenario: Notification-language options are fetched from the backend catalog
- **WHEN** the preferences page loads
- **THEN** it calls `GET /notifications/languages` and renders the returned languages as the `notification_language` control's options, rather than using a hardcoded list
