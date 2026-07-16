## Why

`notification_templates.py` is a hand-rolled, in-Python, per-language string dict — explicitly justified when it covered 2 message kinds ("two message kinds don't justify [a framework]"). It now covers 3 and is growing, and its "message kind" keys (`vehicle_moved`, `ser_ticket_required`, `telegram_linked`) have already drifted from the separate `notification_types` catalog used by the per-user preferences system (`location_moved`, `ser_zone_ticket_required`) — two independently-maintained identities for the same notification kinds. Left as-is, each new notification type means touching a growing nested dict, inventing a new template key that may or may not rhyme with its catalog key, and hoping nothing drifts further. Restructuring now — before more types land — replaces this with a template catalog that scales by adding a self-contained folder per type, and that shares identity with the preferences catalog instead of duplicating it.

## What Changes

- Replace the in-Python `_TEMPLATES` dict with a filesystem-based Jinja2 template catalog: one directory per notification type, one template file per supported language — `templates/<type_key>/<language>.txt.j2`.
- Align template type keys with the existing `notification_types` catalog keys used by the preferences system (`location_moved`, `ser_zone_ticket_required`) instead of the current, differently-named template keys (`vehicle_moved`, `ser_ticket_required`). `telegram_linked` keeps its own folder under the same convention even though it has no catalog row (it's unconditional, not preference-gated).
- `render(type_key, language, **kwargs)` renders via Jinja2 instead of `str.format`. Fallback behavior for `None`/unsupported *user* language preference is unchanged — still falls back to the default language at render time.
- `SUPPORTED_LANGUAGES` is derived from the template directory structure instead of a Python dict's keys.
- Add a fail-fast check (at startup and covered by a test) that every notification type's directory contains a template file for every supported language, so a missing translation is caught before deploy rather than surfacing as a runtime `KeyError`/missing-template error on first use.
- Add `GET /notifications/languages` (authenticated), returning the system's supported language codes.
- Frontend: `PreferencesPage.tsx`'s hardcoded `SUPPORTED_LANGUAGES` array is replaced with a fetch to the new endpoint, so the notification-language dropdown and the backend's validation derive from the same source. No visual or UX change. `frontend/src/i18n.ts`'s app-wide UI locale list (a separate concern — general UI translation, not notification text) is untouched.
- Add `jinja2` as a new backend dependency.

## Capabilities

### New Capabilities
- `notification-templates`: Jinja2-based, per-notification-type, per-language template catalog and rendering mechanism, including the `GET /notifications/languages` endpoint.

### Modified Capabilities
- `notification-channel`: the "Notification templates render localized text for a small, closed set of message kinds" requirement is removed from this capability — that responsibility moves to the new `notification-templates` capability. `notification-channel` retains only channel-transport concerns (Telegram send, account linking, `SendNotification`).
- `user-preferences`: the "Preferences page is visible only when logged in" requirement's `notification_language` control now sources its options from `GET /notifications/languages` instead of a hardcoded frontend list.

## Impact

- **Backend**: new `jinja2` dependency; `src/mobility_manager/application/notification_templates.py` rewritten around a Jinja2 `Environment`; new packaged `templates/` directory (`package_data`/`MANIFEST.in` updated so it ships in the wheel); `NotificationDispatchHandler` and `SerTicketTriggerHandler` update their `render()` call's type-key argument to the aligned catalog key; `notifications.py` router gains the new endpoint; `preferences.py`'s `SUPPORTED_LANGUAGES` import is unchanged as a symbol (same name, new implementation underneath).
- **Frontend**: `PreferencesPage.tsx` fetches available languages instead of hardcoding them; a small addition to the frontend's notifications API module for the new endpoint.
- **Tests**: `tests/application/test_notification_templates.py` updated for the new type-key names and Jinja2-backed rendering; new tests for the fail-fast directory-completeness check and the new endpoint (happy path + anonymous-rejected).
- **No breaking external API changes** — rendered notification text is unchanged; the new endpoint is additive; existing endpoints' request/response shapes are unchanged.
