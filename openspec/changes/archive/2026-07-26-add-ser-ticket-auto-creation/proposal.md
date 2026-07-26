## Why

`UserPreferences.auto_create_ticket` already exists end-to-end (entity, migration, API, UI checkbox) but nothing reads it — toggling it has no effect. Meanwhile, `SerTicketTriggerHandler` only ever notifies a vehicle owner that a SER ticket is required; it never creates one. Users who want the system to just handle SER tickets on their behalf have no way to get that today, and would otherwise keep receiving a "you need a ticket" nudge for a chore they've explicitly asked the system to take off their hands.

## What Changes

- `PUT /preferences` rejects enabling `auto_create_ticket` when the user has no connected SER ticket provider (`UserSerProviderConfigRepository.list_connected_providers` is empty) — 422, with a message telling the user to connect a provider first.
- Enabling `auto_create_ticket` (`false → true`) cascades: `ser_zone_ticket_required` is forced to `enabled=false`; `ser_ticket_created` and `ser_ticket_creation_failed` are forced to `enabled=true` (their first-time defaults). Disabling it (`true → false`) reverses the lock: `ser_zone_ticket_required` becomes togglable again (left as-is, not auto-restored to any prior value), `ser_ticket_created`/`ser_ticket_creation_failed` are forced back to `enabled=false` and locked.
- `PUT /notifications/preferences/{type_key}` rejects (422) enabling `ser_zone_ticket_required` while `auto_create_ticket=true`, and rejects enabling `ser_ticket_created` or `ser_ticket_creation_failed` while `auto_create_ticket=false` — each type is only togglable in the state where it isn't locked.
- Two new `notification_types` catalog rows: `ser_ticket_created`, `ser_ticket_creation_failed` (empty `config_schema` — no movement threshold, they react to an event rather than gating on distance).
- `SerTicketTriggerHandler` is renamed to `SerTicketNotificationTriggerHandler` and gains an early exit: it skips entirely (no obligation notice) when the vehicle owner's `auto_create_ticket` is `true`.
- New `SerTicketCreationTriggerHandler`, subscribed to `VehicleLocationUpdated`, active only when `auto_create_ticket=true`: runs the same zone/exemption check (`FindContainingSerZone` + `DetermineSerTicketRequirement`, unchanged), and when a ticket is required, calls `CreateSerTicket.execute(...)`. `CreateSerTicket` itself is untouched — still exception-based, still used unmodified by the existing manual `POST /parking/ser-tickets` endpoint.
- Two new domain events: `SerTicketCreated` (published on success) and `SerTicketCreationFailed` (published when `CreateSerTicket.execute` raises — carries a user-facing message, not the raw exception/technical detail).
- `SerTicketNotificationTriggerHandler` subscribes to both new events and sends the corresponding notification (gated by each event's own, now-cascaded, preference row): "SER ticket for zone {zone_number} created until {end_date}" on success, a user-facing failure message on failure.
- New Jinja2 i18n templates (all supported languages) for `ser_ticket_created` and `ser_ticket_creation_failed`, following the existing `templates/<type_key>/<language>.txt.j2` convention.
- Frontend: the `ser_zone_ticket_required` checkbox on the preferences page is disabled (greyed out) whenever `auto_create_ticket` is checked, and vice versa for the two new types once they're listed in the notification-types catalog (generic preferences UI already renders any catalog type — no new UI code needed beyond the lock/grey-out behavior, which reads state already fetched via `getPreferences()`).

## Capabilities

### New Capabilities
- `ser-ticket-auto-creation`: automatic SER ticket creation triggered by `VehicleLocationUpdated` when the vehicle owner has opted in, including the `SerTicketCreationTriggerHandler` orchestration, the `SerTicketCreated`/`SerTicketCreationFailed` events, and their notification delivery.

### Modified Capabilities
- `ser-zone-ticket-notification`: `SerTicketTriggerHandler` is renamed to `SerTicketNotificationTriggerHandler` and gains a new early-exit requirement when the owner's `auto_create_ticket` is enabled.
- `notification-type-preferences`: catalog gains two new rows; new cross-field validation and cascade requirements tie `ser_zone_ticket_required`, `ser_ticket_created`, and `ser_ticket_creation_failed` to the `auto_create_ticket` state.
- `user-preferences`: `PUT /preferences` gains a validation requirement (connected provider required to enable `auto_create_ticket`) and a cascade side-effect requirement over the notification-preference rows described above.
- `notification-templates`: two new template directories (`ser_ticket_created`, `ser_ticket_creation_failed`), one file per supported language.

## Impact

- Backend: `preferences.py` and `notification_preferences.py` routers (validation + cascade), `SerTicketTriggerHandler` → `SerTicketNotificationTriggerHandler` (rename + early exit + two new subscribed handler methods), new `SerTicketCreationTriggerHandler`, two new domain event classes, `app.py` wiring (new handler construction + two new `event_publisher.subscribe(...)` calls), alembic migration for the two new catalog rows, new i18n template files.
- Frontend: `PreferencesPage.tsx` (derive `disabled` for the three affected checkboxes from already-fetched `auto_create_ticket` state).
- No changes to `CreateSerTicket`, `DetermineSerTicketRequirement`, `FindContainingSerZone`, or the manual `POST /parking/ser-tickets` endpoint — all reused as-is.
