## Context

`notification_templates.py` currently holds a hand-rolled `dict[str, dict[str, str]]` (`_TEMPLATES[language][kind]`), rendered via `str.format(**kwargs)`. It was deliberately scoped small: `add-vehicle-location-notification/design.md` Decision 6 explicitly rejected "a general i18n/gettext framework" because "two message kinds don't justify that infrastructure," and Decision 7's alternatives-considered explicitly rejected a catalog endpoint for languages because they're "a closed, rarely-changing set of codes." Both of those calls were correct for their scale at the time. There are now 3 message kinds (`vehicle_moved`, `telegram_linked`, `ser_ticket_required`), more are planned, and the growth has already produced a real inconsistency worth fixing on its own: the `notification_types` DB catalog (used by the per-user notification-preferences system, `add-notification-type-preferences`) uses a *different* key namespace for the same notification kinds — `location_moved` and `ser_zone_ticket_required` — than the template dict's `vehicle_moved` and `ser_ticket_required`. This design supersedes Decisions 6 and 7 above: at 3+ growing message kinds and a proven drift between two hand-maintained identity namespaces, the calculus has changed.

Three call sites use `render()` today: `NotificationDispatchHandler`, `SerTicketTriggerHandler`, and the Telegram webhook's link-confirmation path (`notifications.py`). `SUPPORTED_LANGUAGES` is exported from this module as the single source of truth shared with `PUT /preferences`'s `notification_language` validation — that property must be preserved. Separately, the frontend hardcodes its own copy of the same two-language list in `PreferencesPage.tsx` (distinct from `frontend/src/i18n.ts`'s `supportedLngs`, which governs general UI translation, not notification text, and is out of scope here).

## Goals / Non-Goals

**Goals:**
- One canonical identity per notification kind, shared between the `notification_types` preferences catalog and the template catalog, instead of two hand-maintained namespaces.
- Adding a new notification type is self-contained: a new template folder (plus, if it's preference-gated, a new catalog row) — not an edit to a growing central dict.
- A single backend-authoritative source for supported languages, exposed over HTTP so the frontend's notification-language dropdown and the backend's `PUT /preferences` validation can't drift, the same way `available-channels` already does for channels.
- Catch a missing translation (a type folder short one language's file) at startup/test time, not as a runtime error the first time that combination is rendered.
- Preserve `render()`'s existing behavior for a *user's* missing/unrecognized language preference: still falls back to the default language at render time, not an error.

**Non-Goals:**
- Not a general gettext/`.po`/`.mo` i18n framework — no pluralization rules, no ICU message format, no translator-facing extraction tooling. Jinja2 buys structured templates and a real loader, not a localization workflow.
- Not unifying with the frontend's general UI-locale mechanism (`i18n.ts`/`react-i18next`) — that governs the whole app's UI copy and is a separate, already-shipped concern (`add-i18n`).
- No new notification types or message-kind wording changes — this change is the mechanism only; rendered text for the 3 existing kinds is unchanged.
- No database schema changes — `notification_types` already has the right keys; this only aligns the template layer to match it.

## Decisions

### 1. Filesystem layout: by-type, not by-language — `templates/<type_key>/<language>.txt.j2`
Each notification kind gets its own directory containing one file per supported language. Adding a new type touches exactly one new directory; nothing existing is edited. The alternative (grouping by language — `templates/<language>/<type_key>.txt.j2`) mirrors today's nested-dict shape and would keep the exact growth problem this change exists to fix: every new type still means touching N existing per-language locations. A single structured manifest file (YAML/JSON) was also considered and rejected for the same reason — it's still one central file that grows without bound.

### 2. Jinja2 `Environment` with `PackageLoader`, not `FileSystemLoader`
Templates live inside the installed package (`src/mobility_manager/application/templates/`). `PackageLoader("mobility_manager", "application/templates")` resolves correctly whether the package is installed editable or as a built wheel, unlike a path built from `__file__`, which can behave differently across install modes. This requires the `templates/` tree to be declared as package data so it's actually included in the built wheel — `pyproject.toml`'s `[tool.setuptools.package-data]` gets a `"mobility_manager.application" = ["templates/**/*.j2"]` entry (no such config exists today; this is new).

### 3. Template type keys are aligned to the `notification_types` catalog keys
Folder names become `location_moved` and `ser_zone_ticket_required` (renamed from today's `vehicle_moved` and `ser_ticket_required`), matching the catalog exactly. The relationship is one-directional: every `notification_types` catalog row's `key` gets a template folder, but not every template folder needs a catalog row — `telegram_linked` keeps its own folder under the same convention despite having no catalog row, because it's sent unconditionally on successful channel linking, not gated by an opt-in preference (an explicit non-goal from the original notification design). `NotificationDispatchHandler` and `SerTicketTriggerHandler` each already define a `_TYPE_KEY` constant used for the preferences lookup (`"location_moved"`, `"ser_zone_ticket_required"` respectively) — these already match the new template keys, so `render()`'s call in each handler switches from a separately-typed literal (`"vehicle_moved"`, `"ser_ticket_required"`) to reusing `_TYPE_KEY`, collapsing two previously-independent literals into one.

**Alternative considered**: keep template keys as-is and add a separate mapping dict from catalog key to template key. Rejected — that's exactly the kind of extra indirection that caused the drift in the first place; a second lookup table is one more thing to keep in sync.

### 4. `SUPPORTED_LANGUAGES` derived from the template directory structure, with an equal-coverage invariant enforced at import time
At module import, scan `templates/*/` and collect each type-folder's set of language codes (from filenames). All type folders are required to have an *identical* set of language codes — if any folder's set differs from the others, import raises immediately with an error naming the offending type and the missing language, rather than deferring discovery to whichever render() call happens to hit it first at runtime. `SUPPORTED_LANGUAGES` becomes that common set (a `frozenset`, same public shape as today). This keeps "which languages does this system support" an unambiguous, single-valued fact rather than something that could vary silently per notification kind.

This is a stricter invariant than today's implicit one (a missing `_TEMPLATES[lang][key]` entry currently raises a `KeyError` inside `render()`, i.e. only ever discovered when that exact kind+language combination is first rendered — which for a rare kind could be a long time after a bad deploy). Import-time (i.e., app-startup-time) validation is preferred over a separate CLI/CI-only check because this module is already imported eagerly by the handlers and routers at process startup — there's no meaningfully "later" fail-fast point to defer to.

### 5. `render(type_key, language, **kwargs) -> str` signature is unchanged; internals swap `str.format` for `Template.render`
All three call sites keep calling `render()` exactly as today. Jinja2 autoescaping is explicitly left **off** (the default for a non-`.html`/`.xml` template name, but stated explicitly rather than relied upon implicitly) — output is plain text delivered to Telegram/push channels, not HTML, so there's no injection context autoescaping would protect against, and turning it on would incorrectly HTML-entity-escape things like an SER zone number or a plate.

### 6. New endpoint: `GET /notifications/languages`
Same file (`notifications.py`), same authenticated-GET-returns-a-flat-catalog-list shape as `available-channels` (`{"languages": ["en", "es"]}`), sourced directly from `SUPPORTED_LANGUAGES`. Named `languages` rather than `available-languages` — there is no per-user "configured languages" concept for it to be disambiguated from (unlike channels, which has both `channels` (a user's configured set) and `available-channels` (the full catalog)), so the shorter, RESTful name is unambiguous on its own. Placed alongside `available-channels` for router-file consistency even though the capability boundary (`notification-templates` vs `notification-channel`) differs — router-file organization and capability-spec organization aren't required to match, and this file already imports from `notification_templates` today.

### 7. Frontend: fetch instead of hardcode, no visual change
`frontend/src/api/notifications.ts` gains a function mirroring the existing `fetchAvailableChannels` (used today by `NotificationChannelsPage.tsx`); `PreferencesPage.tsx`'s hardcoded `const SUPPORTED_LANGUAGES = ["en", "es"]` is replaced with fetched state populated the same way `NotificationChannelsPage.tsx` populates `availableChannels`. `i18n.ts` is untouched.

## Risks / Trade-offs

- **[Risk] Import-time validation can crash app startup (or test collection) if the template catalog is ever inconsistent.** → Intended behavior: a broken template catalog should prevent the app from starting, the same way a broken migration would, with a clear error naming the missing (type, language) pair — better than a silent English-only fallback for a language a user has actually selected.
- **[Risk] `jinja2` is a new dependency for what today is 3 one-line templates.** → It's a small, extremely widely-used, actively maintained library commonly already present transitively in Python web stacks; the payoff is the scaling story this change exists to deliver, not the current 3 templates in isolation.
- **[Risk] Packaging `templates/` into the built wheel is easy to get subtly wrong (works from source tree, silently missing in an installed package).** → Covered explicitly in tasks.md: a test/verification step that exercises the package as installed, not just importable from the source checkout.
- **[Risk] This formally reverses two named decisions in `add-vehicle-location-notification/design.md`.** → Addressed by stating the supersession explicitly in this document's Context section rather than silently diverging from it.

## Migration Plan

1. Add `jinja2` to `pyproject.toml` dependencies; add `package-data` config for `templates/**/*.j2`.
2. Create `templates/location_moved/{en,es}.txt.j2`, `templates/ser_zone_ticket_required/{en,es}.txt.j2`, `templates/telegram_linked/{en,es}.txt.j2` with today's exact wording (content unchanged, only the mechanism changes).
3. Rewrite `notification_templates.py`: Jinja2 `Environment` + `PackageLoader`, import-time directory-coverage validation, `render()` via `Template.render(**kwargs)`.
4. Update `NotificationDispatchHandler` and `SerTicketTriggerHandler` to pass their existing `_TYPE_KEY` constant into `render()` instead of a separate literal.
5. Add `GET /notifications/languages` + response model in `notifications.py`.
6. Update `tests/application/test_notification_templates.py` for the renamed keys and Jinja2-backed rendering (happy path per kind/language, `None`/unsupported-language fallback, and the new fail-fast coverage check); add endpoint tests (happy path + anonymous-rejected).
7. Frontend: add the fetch function, wire it into `PreferencesPage.tsx`, remove the hardcoded array.
8. Full backend test suite, frontend lint, and a build/install smoke check that the packaged templates are present.

**Rollback**: revert the commit(s). No database/data migration is involved, so nothing to undo beyond the code change itself.

## Open Questions

None blocking — ready for task breakdown.
