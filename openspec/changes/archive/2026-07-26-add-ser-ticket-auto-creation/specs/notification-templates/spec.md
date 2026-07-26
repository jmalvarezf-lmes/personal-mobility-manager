## ADDED Requirements

### Requirement: Template catalog covers ser_ticket_created and ser_ticket_creation_failed
The system SHALL provide `templates/ser_ticket_created/<language>.txt.j2` and `templates/ser_ticket_creation_failed/<language>.txt.j2` for every language in `SUPPORTED_LANGUAGES`, following the same one-directory-per-type, one-file-per-language convention as every other catalog-backed notification kind. The `ser_ticket_created` template SHALL render using `zone_number`, `start_date`, and `end_date` substitution values — the latter two already formatted as strings in the owner's timezone by the caller, not raw `datetime` objects — stating that a SER ticket for that zone is valid from `start_date` to `end_date`. The `ser_ticket_creation_failed` template SHALL render using only `zone_number` — no exception message or `reason` value is ever passed into its context — stating that automatic ticket creation failed for that zone and the user must create one manually.

#### Scenario: Renders the ticket-created kind with zone, start date, and end date
- **WHEN** `render()` is called with `type_key="ser_ticket_created"`, a supported language, and substitution values including the zone number and the already-localized start and end date strings
- **THEN** it returns text in that language stating a SER ticket for that zone is valid from that start date to that end date

#### Scenario: Renders the creation-failed kind without any technical detail
- **WHEN** `render()` is called with `type_key="ser_ticket_creation_failed"`, a supported language, and a zone number
- **THEN** it returns text in that language stating automatic creation failed for that zone and it must be created manually, with no exception message or reason code interpolated

#### Scenario: Missing-language import check still applies to the two new types
- **WHEN** the template catalog is loaded
- **THEN** `ser_ticket_created` and `ser_ticket_creation_failed` are included in the same import-time language-coverage validation as every other type directory — a missing language file for either fails import, not deferred to the first `render()` call
