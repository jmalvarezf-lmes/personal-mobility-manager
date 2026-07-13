## MODIFIED Requirements

### Requirement: Notification templates render localized text for a small, closed set of message kinds
The system SHALL provide a notification-template rendering function accepting a message kind, a language code (or `None`), and keyword substitution values, returning the rendered text for that kind in the given language. If the language is `None` or not among the supported languages, the function SHALL render using a default language rather than raising. This mechanism SHALL NOT be a general-purpose i18n framework (no `.po`/`.mo` compilation, no `gettext` dependency) — it covers exactly the message kinds this system defines, which now includes a "SER ticket required" kind alongside the existing "vehicle moved" and "telegram linked" kinds.

#### Scenario: Renders a known kind in a supported language
- **WHEN** the template function is called with a message kind and a supported language code, plus any required substitution values
- **THEN** it returns that kind's text rendered in that language with the values substituted

#### Scenario: Unset or unsupported language falls back to the default
- **WHEN** the template function is called with `language=None` or a language code not among the supported set
- **THEN** it returns that kind's text rendered in the default language, without raising

#### Scenario: Renders the SER-ticket-required kind with the vehicle's plate and zone number
- **WHEN** the template function is called with the SER-ticket-required message kind, a supported language code, and substitution values including the vehicle's plate and the SER zone number
- **THEN** it returns text in that language stating that a SER ticket must be created, including the plate and zone number
