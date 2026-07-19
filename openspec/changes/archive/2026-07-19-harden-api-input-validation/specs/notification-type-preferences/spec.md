## MODIFIED Requirements

### Requirement: Authenticated user can update a single notification type's preference
The system SHALL expose `PUT /notifications/preferences/{type_key}`, requiring an authenticated session, accepting `enabled` (bool) and `config` (object), replacing both fields for that user's `(user_id, type_key)` row. The system SHALL reject a `type_key` not present in `notification_types`, and SHALL reject a `config` that does not conform to that type's `config_schema` — conformance means every field `config` declares matches that field's rules in `config_schema` (type and bounds), AND `config` contains no key absent from `config_schema` (an unrecognized key is a conformance failure, not silently ignored).

#### Scenario: Logged-in user disables a notification type
- **WHEN** an authenticated user sends `PUT /notifications/preferences/ser_zone_ticket_required` with `enabled: false, config: {}`
- **THEN** the response is `200 OK`
- **THEN** a subsequent `GET /notifications/preferences` shows `ser_zone_ticket_required` as `enabled: false`

#### Scenario: Logged-in user customizes a threshold
- **WHEN** an authenticated user sends `PUT /notifications/preferences/location_moved` with `enabled: true, config: {"threshold_m": 20}`
- **THEN** the response is `200 OK` with `config.threshold_m` equal to `20`
- **THEN** a subsequent `GET /notifications/preferences` reflects `threshold_m: 20` for `location_moved`

#### Scenario: Unknown type_key is rejected
- **WHEN** an authenticated user sends `PUT /notifications/preferences/unknown_type`
- **THEN** the response is `404 Not Found` and no row is created or changed

#### Scenario: Config failing the type's schema is rejected
- **WHEN** an authenticated user sends `PUT /notifications/preferences/location_moved` with `config: {"threshold_m": -5}`
- **THEN** the response is `422 Unprocessable Entity` and the existing row is unchanged

#### Scenario: Config with an unrecognized key is rejected
- **WHEN** an authenticated user sends `PUT /notifications/preferences/location_moved` with `config: {"threshold_m": 20, "unexpected_field": "value"}`
- **THEN** the response is `422 Unprocessable Entity` and the existing row is unchanged

#### Scenario: Anonymous request is rejected
- **WHEN** a request without a valid session cookie sends `PUT /notifications/preferences/{type_key}`
- **THEN** the response is `401 Unauthorized`
