## MODIFIED Requirements

### Requirement: Authenticated user can update their preferences
The system SHALL expose `PUT /preferences`, requiring an authenticated session, accepting `default_ticket_duration_minutes` (int, > 0), `auto_create_ticket` (bool), `preferred_notification_channel` (str or null), `notification_language` (str or null), and `timezone` (str or null), replacing all five values for the current user. The system SHALL reject a `preferred_notification_channel` value that does not correspond to a channel the current user has configured. The system SHALL reject a `notification_language` value that is not among the system's supported languages. The system SHALL reject a `timezone` value that is not a recognized IANA timezone identifier (validated against `zoneinfo.available_timezones()`). `null` is always accepted for `preferred_notification_channel`, `notification_language`, and `timezone`, and clears the corresponding preference.

The system SHALL reject (`422 Unprocessable Entity`, no values changed) a request setting `auto_create_ticket: true` for a user with no connected SER ticket provider (`UserSerProviderConfigRepository.list_connected_providers` returns an empty list), with a message telling the user to connect a provider first.

When `auto_create_ticket` transitions `false → true` as part of a successful update, the system SHALL, in the same request, force the user's `ser_zone_ticket_required` notification preference to `enabled=false` and force `ser_ticket_created` and `ser_ticket_creation_failed` to `enabled=true` (their rows are created via `ensure_defaults` first if absent). When `auto_create_ticket` transitions `true → false`, the system SHALL force `ser_ticket_created` and `ser_ticket_creation_failed` to `enabled=false`, and SHALL leave `ser_zone_ticket_required` at whatever value it already has (not automatically re-enabled). When `auto_create_ticket` does not change value, no `user_notification_preferences` row is modified as a side effect of the request.

#### Scenario: Logged-in user updates preferences
- **WHEN** an authenticated user sends `PUT /preferences` with `default_ticket_duration_minutes: 90`, `auto_create_ticket: true`, `preferred_notification_channel: "telegram"` (a channel they have connected), `notification_language: "es"`, and `timezone: "Europe/Madrid"`
- **THEN** the response is `200 OK` with the updated values
- **THEN** a subsequent `GET /preferences` reflects the new values

#### Scenario: Invalid duration is rejected
- **WHEN** an authenticated user sends `PUT /preferences` with `default_ticket_duration_minutes: 0` or a negative number
- **THEN** the response is `422 Unprocessable Entity` and no values are changed

#### Scenario: Preferred channel not configured by the user is rejected
- **WHEN** an authenticated user sends `PUT /preferences` with `preferred_notification_channel` set to a channel they have not connected
- **THEN** the response is `422 Unprocessable Entity` and no values are changed

#### Scenario: Clearing the preferred channel is allowed
- **WHEN** an authenticated user sends `PUT /preferences` with `preferred_notification_channel: null`
- **THEN** the response is `200 OK` and the user's `preferred_notification_channel` becomes unset

#### Scenario: Unrecognized notification_language value is rejected
- **WHEN** an authenticated user sends `PUT /preferences` with `notification_language` set to a value not among the system's supported languages
- **THEN** the response is `422 Unprocessable Entity` and no values are changed

#### Scenario: Clearing the notification language is allowed
- **WHEN** an authenticated user sends `PUT /preferences` with `notification_language: null`
- **THEN** the response is `200 OK` and the user's `notification_language` becomes unset

#### Scenario: Unrecognized timezone value is rejected
- **WHEN** an authenticated user sends `PUT /preferences` with `timezone` set to a string that is not a recognized IANA timezone identifier
- **THEN** the response is `422 Unprocessable Entity` and no values are changed

#### Scenario: Valid timezone is accepted
- **WHEN** an authenticated user sends `PUT /preferences` with `timezone: "Europe/Madrid"`
- **THEN** the response is `200 OK` and the user's `timezone` becomes `"Europe/Madrid"`

#### Scenario: Clearing the timezone is allowed
- **WHEN** an authenticated user sends `PUT /preferences` with `timezone: null`
- **THEN** the response is `200 OK` and the user's `timezone` becomes unset

#### Scenario: Anonymous request is rejected
- **WHEN** a request without a valid session cookie sends `PUT /preferences`
- **THEN** the response is `401 Unauthorized`

#### Scenario: Enabling auto_create_ticket without a connected SER provider is rejected
- **WHEN** an authenticated user with no connected SER ticket provider sends `PUT /preferences` with `auto_create_ticket: true`
- **THEN** the response is `422 Unprocessable Entity` and no values are changed, including `auto_create_ticket` itself

#### Scenario: Enabling auto_create_ticket cascades the related notification preferences
- **WHEN** an authenticated user with a connected SER ticket provider sends `PUT /preferences` changing `auto_create_ticket` from `false` to `true`
- **THEN** the response is `200 OK`
- **THEN** the user's `ser_zone_ticket_required` notification preference becomes `enabled: false`
- **THEN** the user's `ser_ticket_created` and `ser_ticket_creation_failed` notification preferences become `enabled: true`

#### Scenario: Disabling auto_create_ticket cascades the related notification preferences
- **WHEN** an authenticated user sends `PUT /preferences` changing `auto_create_ticket` from `true` to `false`
- **THEN** the response is `200 OK`
- **THEN** the user's `ser_ticket_created` and `ser_ticket_creation_failed` notification preferences become `enabled: false`
- **THEN** the user's `ser_zone_ticket_required` notification preference is left unchanged from whatever it already was

#### Scenario: Leaving auto_create_ticket unchanged does not cascade
- **WHEN** an authenticated user sends `PUT /preferences` with `auto_create_ticket` equal to its current stored value
- **THEN** no `user_notification_preferences` row is modified as a side effect of this request

---

### Requirement: Preferences page is visible only when logged in
The system SHALL provide a frontend "Preferences" page, reachable only via a protected route, that lets the user view and edit `default_ticket_duration_minutes`, `auto_create_ticket`, `preferred_notification_channel`, `notification_language`, and `timezone`. The `preferred_notification_channel` control SHALL only offer choices among the channels the user currently has connected (per `GET /notifications/channels`), plus an option to clear the preference. The `notification_language` control SHALL offer the system's supported languages, sourced from `GET /notifications/languages` rather than a hardcoded frontend list, so the offered options and the backend's `PUT /preferences` validation cannot drift apart. The `timezone` control SHALL be a searchable picker listing every IANA zone returned by `Intl.supportedValuesOf('timeZone')`, each labeled with its zone name and current UTC offset/abbreviation (e.g. "Europe/Madrid (CEST)"), plus an option to clear the preference back to unset.

When saving fails because `PUT /preferences` rejects enabling `auto_create_ticket` for having no connected SER ticket provider, the page SHALL surface that rejection's message to the user (e.g. via the same error area used for other save failures) rather than a generic error.

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

#### Scenario: Logged-in user picks a timezone
- **WHEN** an authenticated user searches for and selects a timezone (e.g. by typing "Madrid") and saves
- **THEN** the page calls `PUT /preferences` with that zone's IANA identifier as `timezone`
- **THEN** the page reflects the saved value on success

#### Scenario: Logged-in user clears their timezone preference
- **WHEN** an authenticated user clears the timezone control and saves
- **THEN** the page calls `PUT /preferences` with `timezone: null`

#### Scenario: Enabling auto-create without a connected provider shows a clear error
- **WHEN** an authenticated user with no connected SER ticket provider checks `auto_create_ticket` and saves
- **THEN** `PUT /preferences` is called, returns `422`, and the page displays a message telling the user to connect a provider first — the checkbox's on-screen state is not silently reverted without explanation
