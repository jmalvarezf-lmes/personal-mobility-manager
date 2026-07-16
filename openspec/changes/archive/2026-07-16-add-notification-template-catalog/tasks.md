## 1. Dependencies & packaging

- [x] 1.1 Add `jinja2` to `pyproject.toml` dependencies
- [x] 1.2 Add `[tool.setuptools.package-data]` (or equivalent) entry so `application/templates/**/*.j2` ships in the built package
- [x] 1.3 Sync/install dependencies in the dev environment

## 2. Template catalog files

- [x] 2.1 Create `src/mobility_manager/application/templates/location_moved/{en,es}.txt.j2` with today's exact `vehicle_moved` wording (content unchanged, only relocated/renamed)
- [x] 2.2 Create `src/mobility_manager/application/templates/ser_zone_ticket_required/{en,es}.txt.j2` with today's exact `ser_ticket_required` wording
- [x] 2.3 Create `src/mobility_manager/application/templates/telegram_linked/{en,es}.txt.j2` with today's exact wording

## 3. Rendering mechanism

- [x] 3.1 Rewrite `notification_templates.py`: build a Jinja2 `Environment` using `PackageLoader("mobility_manager", "application/templates")`, autoescaping explicitly disabled
- [x] 3.2 Implement import-time directory-coverage validation: scan `templates/*/`, assert every type directory has an identical set of language files, raise a clear error naming the offending type and missing language on mismatch
- [x] 3.3 Derive `SUPPORTED_LANGUAGES` (frozenset) from the validated directory scan
- [x] 3.4 Implement `render(type_key: str, language: str | None, **kwargs) -> str`, resolving `templates/<type_key>/<language>.txt.j2` (or the default language's template when `language` is `None`/unsupported) and rendering via `Template.render(**kwargs)`

## 4. Call-site updates

- [x] 4.1 `NotificationDispatchHandler`: change its `render(...)` call to pass its existing `_TYPE_KEY` constant (`"location_moved"`) instead of the literal `"vehicle_moved"`
- [x] 4.2 `SerTicketTriggerHandler`: change its `render(...)` call to pass its existing `_TYPE_KEY` constant (`"ser_zone_ticket_required"`) instead of the literal `"ser_ticket_required"`
- [x] 4.3 Confirm `notifications.py`'s Telegram webhook `render("telegram_linked", ...)` call needs no key change

## 5. New endpoint

- [x] 5.1 Add a `NotificationLanguagesResponse` model (same flat-list catalog-response shape as `available-channels`'s response)
- [x] 5.2 Add `GET /notifications/languages` to `notifications.py` — authenticated, returns `{"languages": [...]}` sourced from `SUPPORTED_LANGUAGES`
- [x] 5.3 Update `notifications.py`'s module docstring to list the new endpoint alongside the existing ones

## 6. Frontend

- [x] 6.1 Add a `getAvailableLanguages` function to `frontend/src/api/notifications.ts`, mirroring the existing `getAvailableChannels` (tasks.md referred to it as `fetchAvailableChannels`; the actual existing function is named `getAvailableChannels` — followed the real codebase naming convention, `get*`, for consistency)
- [x] 6.2 Update `PreferencesPage.tsx` to fetch available languages into state (same pattern `NotificationChannelsPage.tsx` uses for `availableChannels`), removing the hardcoded `SUPPORTED_LANGUAGES` array
- [x] 6.3 Confirm `frontend/src/i18n.ts` is untouched (general UI locale list stays independent)

## 7. Backend tests — happy paths and corner cases

- [x] 7.1 Update `tests/application/test_notification_templates.py`: rename `type_key` literals used across existing tests (`vehicle_moved` → `location_moved`, `ser_ticket_required` → `ser_zone_ticket_required`)
- [x] 7.2 Keep/verify happy-path coverage: known kind renders correctly in each supported language with substitution (`location_moved`, `ser_zone_ticket_required`, `telegram_linked` with no substitution)
- [x] 7.3 Keep/verify corner case: `language=None` falls back to the default language without raising
- [x] 7.4 Keep/verify corner case: an unrecognized language falls back to the default language without raising
- [x] 7.5 Keep/verify `SUPPORTED_LANGUAGES` contains `en` and `es`
- [x] 7.6 Add corner-case test: a type directory missing one supported language's template file causes catalog loading to raise, naming the type and the missing language (exercise the validation function directly against a temporary/fixture template tree rather than mutating the real package data)
- [x] 7.7 Add tests for `GET /notifications/languages`: happy path (`200` with `{"languages": ["en", "es"]}`) and corner case (anonymous request → `401`)
- [x] 7.8 Re-run `tests/application/event_handlers/test_notification_dispatch_handler.py` and `test_ser_ticket_trigger_handler.py` unchanged — both already assert on rendered *text* and use the catalog-aligned `_TYPE_KEY` values for preferences setup, so they should pass without edits; confirmed: both pass unmodified

## 8. Packaging verification

- [x] 8.1 Build the package (or `pip install .` into a clean venv) and confirm the templates are present and `render()` works from the installed package, not just the source checkout

## 9. Full verification

- [x] 9.1 Run `ruff check` and `mypy --strict`
- [x] 9.2 Run the full backend test suite
- [x] 9.3 Run frontend lint/typecheck
- [x] 9.4 Manual/E2E smoke check that `PreferencesPage.tsx`'s notification-language dropdown still shows the same options with no visual change, now sourced from the new endpoint (best-effort verification only — no live browser/backend+DB available in this environment to run the actual `preferences.spec.ts` Playwright test; verified instead via: `tsc --noEmit` type-check passing, response shape `{"languages": ["en","es"]}` matching `NotificationLanguagesResponse`/frontend interface exactly, and the existing `page.preferences.languages.{en,es}` translation keys already present in both locale files unchanged. A real browser/E2E pass of `frontend/e2e/preferences.spec.ts` against a running backend+DB is recommended as a follow-up before merge.)
