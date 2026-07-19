## ADDED Requirements

### Requirement: Request bodies reject unknown fields
The system SHALL reject, with `422 Unprocessable Entity`, any JSON request body containing a field not declared on that endpoint's request schema. This applies to every endpoint that accepts a request body.

#### Scenario: Extra field on a known endpoint is rejected
- **WHEN** a client sends `POST /vehicles` with a valid `RegisterGenericRequest` body plus an additional field not declared on that schema (e.g. `"is_admin": true`)
- **THEN** the response is `422 Unprocessable Entity` and no vehicle is created

#### Scenario: Request with only declared fields succeeds
- **WHEN** a client sends a request body containing only fields declared on the endpoint's schema
- **THEN** the request is processed normally and no `422` is raised for field presence

### Requirement: VIN format is validated
The system SHALL validate that a submitted `vin` matches the ISO 3779 shape — exactly 17 characters, uppercase alphanumeric, excluding `I`, `O`, and `Q` — and SHALL reject a non-conforming value with `422`.

#### Scenario: Malformed VIN is rejected
- **WHEN** a client sends `POST /vehicles` with `brand: "toyota"` and a `vin` that is not 17 characters or contains a disallowed character (`I`, `O`, `Q`, or any non-alphanumeric character)
- **THEN** the response is `422 Unprocessable Entity`

#### Scenario: Well-formed VIN is accepted
- **WHEN** a client sends `POST /vehicles` with a `vin` that is exactly 17 uppercase alphanumeric characters excluding `I`, `O`, `Q`
- **THEN** the request proceeds past VIN validation (subject to any other validation on the request)

### Requirement: Toyota locale is validated against the provider library's known locales
The system SHALL validate a submitted Toyota `locale` using `pytoyoda`'s locale validation, and SHALL reject an unrecognized locale with `422`.

#### Scenario: Unknown locale is rejected
- **WHEN** a client sends a Toyota vehicle register or update request with a `locale` value `pytoyoda` does not recognize as valid
- **THEN** the response is `422 Unprocessable Entity`

#### Scenario: Known locale is accepted
- **WHEN** a client sends a Toyota vehicle register or update request with a `locale` value `pytoyoda` recognizes as valid
- **THEN** the request proceeds past locale validation (subject to any other validation on the request)

### Requirement: Unconstrained text fields carry a defensive maximum length
The system SHALL enforce a maximum length on request fields that have no stricter format rule, rejecting an over-length value with `422`. This applies at minimum to: Toyota `username` and `password` (register and update), `display_name` (register and update), and `city_code` (SER parking exemption).

#### Scenario: Over-length display_name is rejected
- **WHEN** a client sends a vehicle register or update request with `display_name` longer than its configured maximum
- **THEN** the response is `422 Unprocessable Entity`

#### Scenario: Within-bound value is accepted
- **WHEN** a client sends a request with `display_name`, Toyota `username`/`password`, or `city_code` at or under its configured maximum length
- **THEN** the request proceeds past that length check (subject to any other validation on the request)

### Requirement: Path-parameter identifiers are validated against known values before use
The system SHALL validate the `provider` path parameter on `DELETE /ser-ticket-providers/connections/{provider}` and the `channel` path parameter on `DELETE /notifications/channels/{channel}` against their respective live known-value sets (the set of supported SER ticket providers; `app.state.notification_channels`'s registered keys) before invoking the corresponding use case, returning `404` for an unrecognized value.

#### Scenario: Unknown provider is rejected before reaching the use case
- **WHEN** a client sends `DELETE /ser-ticket-providers/connections/{provider}` with a `provider` value that is not a supported SER ticket provider
- **THEN** the response is `404 Not Found` and the disconnect use case is not invoked

#### Scenario: Unknown channel is rejected before reaching the use case
- **WHEN** a client sends `DELETE /notifications/channels/{channel}` with a `channel` value not present in the running system's registered notification channels
- **THEN** the response is `404 Not Found` and the remove-channel use case is not invoked

#### Scenario: Known provider or channel proceeds normally
- **WHEN** a client sends either delete request with a value present in the corresponding known-value set
- **THEN** the request proceeds to the use case as before
