## ADDED Requirements

### Requirement: Template catalog is organized by notification type, one directory per type, one file per supported language
The system SHALL organize notification message templates as a Jinja2 template catalog on disk, structured as one directory per notification kind (`type_key`) containing one template file per supported language (`templates/<type_key>/<language>.txt.j2`). Directory names for notification kinds that have a corresponding `notification_types` catalog row SHALL match that row's `key` exactly. Not every template directory requires a matching catalog row — a notification kind sent unconditionally (not gated by a per-user preference) may have a template directory with no corresponding catalog entry.

#### Scenario: Preference-gated kinds share their catalog key as template directory name
- **WHEN** a notification kind is preference-gated (has a `notification_types` catalog row)
- **THEN** its template directory name is exactly that row's `key` (e.g. `location_moved`, `ser_zone_ticket_required`)

#### Scenario: Unconditional kinds still follow the same directory convention
- **WHEN** a notification kind is sent unconditionally and has no `notification_types` catalog row (e.g. `telegram_linked`)
- **THEN** it still has its own template directory following the same `<type_key>/<language>.txt.j2` convention

---

### Requirement: render() renders localized notification text for a known type and language
The system SHALL provide a `render(type_key: str, language: str | None, **kwargs) -> str` function that resolves the Jinja2 template at `templates/<type_key>/<language>.txt.j2`, falling back to the default language's template when `language` is `None` or not among `SUPPORTED_LANGUAGES`, and renders it with `kwargs` as the template context. This mechanism SHALL NOT be a general-purpose i18n framework (no `.po`/`.mo` compilation, no `gettext` dependency, no pluralization support) — it covers exactly the notification kinds this system defines.

#### Scenario: Renders a known kind in a supported language with substitution
- **WHEN** `render()` is called with a known `type_key`, a supported language, and the substitution values that kind's template requires
- **THEN** it returns that kind's text rendered in that language with the values substituted

#### Scenario: Unset or unsupported language falls back to the default language
- **WHEN** `render()` is called with `language=None` or a language not among `SUPPORTED_LANGUAGES`
- **THEN** it returns that kind's text rendered in the default language, without raising

#### Scenario: Renders the SER-zone-ticket-required kind with the vehicle's plate and zone number
- **WHEN** `render()` is called with `type_key="ser_zone_ticket_required"`, a supported language, and substitution values including the vehicle's plate and the SER zone number
- **THEN** it returns text in that language stating that a SER ticket must be created, including the plate and zone number

#### Scenario: Renders a kind with no substitution values
- **WHEN** `render()` is called with `type_key="telegram_linked"` and a supported language, with no additional keyword arguments
- **THEN** it returns that kind's fixed text in that language

---

### Requirement: SUPPORTED_LANGUAGES is derived from the template catalog and validated for equal coverage at import time
The system SHALL derive `SUPPORTED_LANGUAGES` from the set of language codes present in the template catalog, and SHALL validate at module import time that every notification-type directory contains a template file for every language in that set. If any type directory is missing a language present in another type directory, import SHALL fail with an error identifying the type and the missing language, rather than deferring discovery to the first `render()` call for that combination. `SUPPORTED_LANGUAGES` remains the single source of truth shared between rendering and `PUT /preferences`'s `notification_language` validation.

#### Scenario: All type directories have matching language coverage
- **WHEN** the template catalog is loaded and every type directory contains the same set of language files
- **THEN** `SUPPORTED_LANGUAGES` equals that common set and import succeeds

#### Scenario: A type directory missing a language fails fast at import time
- **WHEN** one notification type's directory is missing a template file for a language present in another type's directory
- **THEN** importing the template catalog raises an error identifying the type and the missing language, before any `render()` call is made

---

### Requirement: Authenticated user can list the system's supported notification languages
The system SHALL expose `GET /notifications/languages`, requiring an authenticated session, returning `{"languages": [<language codes>]}` — the current value of `SUPPORTED_LANGUAGES`.

#### Scenario: Returns the supported languages
- **WHEN** an authenticated user calls `GET /notifications/languages`
- **THEN** the response is `200 OK` with `{"languages": ["en", "es"]}`

#### Scenario: Anonymous request is rejected
- **WHEN** a request without a valid session cookie is sent to `GET /notifications/languages`
- **THEN** the response is `401 Unauthorized`
