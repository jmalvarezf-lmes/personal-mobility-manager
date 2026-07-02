## Context

The frontend is a React 19 + TypeScript + Vite app with ~45 hardcoded English strings spread across 7 files (Nav, LandingPage, MapPage, MyVehiclesPage, AddVehicleModal, EditVehicleModal, VehicleCard). There is no i18n infrastructure. One string (`"Cargando zonas…"` in MapPage) is already Spanish — a bug to fix.

## Goals / Non-Goals

**Goals:**
- Detect browser language automatically and render in English or Spanish.
- Allow users to override the language via a Nav selector persisted in `localStorage`.
- Replace all hardcoded UI strings with `t()` calls.
- Keep E2E tests stable by forcing English in Playwright fixtures.

**Non-Goals:**
- Translating backend API error messages.
- Supporting more than 2 languages (en, es) in this change.
- Server-side language detection or `Accept-Language` header handling.
- RTL layout support.

## Decisions

### Decision: react-i18next over react-intl or a custom context

**Chosen**: `react-i18next` + `i18next-browser-languagedetector` + `i18next-http-backend`.

**Why**: react-i18next is the dominant React i18n solution. `i18next-browser-languagedetector` handles all browser detection heuristics in one import. `i18next-http-backend` lazy-loads translation files from `public/locales/` as static assets — the Spanish bundle is only downloaded when needed.

**Alternatives considered**:
- `react-intl` (FormatJS): ICU message format is more powerful but significantly more verbose; overkill for 45 strings.
- Custom React context: zero deps but requires hand-rolling pluralization, date formatting, and lazy loading as the app grows.

---

### Decision: One flat namespace per language (`translation.json`)

**Chosen**: Single `translation.json` per locale, grouped by feature prefix (`nav.*`, `page.*`, `modal.*`, `vehicle.*`, `common.*`).

**Why**: 45 strings don't justify the overhead of splitting across multiple namespace files. A single file per locale is the i18next default and easiest to manage. Feature prefixes give logical structure without the runtime cost of multi-namespace loading.

**Alternatives considered**: Separate namespace files per component (`nav.json`, `vehicles.json`, etc.) — valid at scale but unnecessary here.

---

### Decision: Language selector in Nav as a `<select>` element

**Chosen**: `<select>` with options `en` / `es` rendered in the navigation bar, alongside existing nav items.

**Why**: Simple, accessible, no extra dependency. The selector shows the current language pre-selected (from `i18next.language`) and calls `i18next.changeLanguage(val)` on change. i18next-browser-languagedetector's `localStorage` cache backend ensures the choice persists automatically.

**Alternatives considered**: Flag icons or a dropdown menu — more visual but add complexity and are controversial for language switching (flags represent countries, not languages).

---

### Decision: Force `lng=en` in Playwright fixtures via localStorage

**Chosen**: In `frontend/e2e/fixtures/auth.ts`, call `page.evaluate(() => localStorage.setItem('i18nextLng', 'en'))` before navigating to the app.

**Why**: Headless Chromium's `navigator.language` is typically `en-US` already, but this is an environment detail that could change. Explicitly setting `i18nextLng` in localStorage guarantees the test environment is English regardless of CI runner configuration. It uses the exact key that `i18next-browser-languagedetector`'s `localStorage` detector reads.

**Alternatives considered**: Passing `?lng=en` query param — also works but requires every test URL to carry it; localStorage is cleaner.

---

### Decision: Translation key naming convention

Keys use dot-separated feature prefix + descriptor: `feature.context.label`.

```
common.cancel          → "Cancel" / "Cancelar"
common.displayName     → "Display Name" / "Nombre"
nav.title              → "Personal Mobility Manager"
nav.map                → "Map" / "Mapa"
nav.myVehicles         → "My Vehicles" / "Mis vehículos"
nav.logout             → "Logout" / "Cerrar sesión"
nav.loginGoogle        → "Login with Google" / "Iniciar sesión con Google"
nav.language           → "Language" / "Idioma"
page.landing.title     → "Personal Mobility Manager"
page.myVehicles.title  → "My Vehicles" / "Mis vehículos"
page.myVehicles.add    → "Add Vehicle" / "Añadir vehículo"
page.myVehicles.empty  → "No vehicles registered yet." / "Aún no hay vehículos registrados."
page.myVehicles.loading → "Loading vehicles…" / "Cargando vehículos…"
page.map.loading       → "Loading map data…" / "Cargando datos del mapa…"
modal.addVehicle.title → "Add Vehicle" / "Añadir vehículo"
modal.addVehicle.brand → "Brand" / "Marca"
modal.addVehicle.brandGeneric → "Generic" / "Genérico"
modal.addVehicle.brandToyota  → "Toyota"
modal.addVehicle.adding       → "Adding…" / "Añadiendo…"
modal.addVehicle.add          → "Add" / "Añadir"
modal.editVehicle.title       → "Edit Vehicle" / "Editar vehículo"
modal.editVehicle.saving      → "Saving…" / "Guardando…"
modal.editVehicle.save        → "Save" / "Guardar"
modal.editVehicle.newPassword → "New Password" / "Nueva contraseña"
modal.editVehicle.keepBlank   → "(leave blank to keep current)" / "(dejar en blanco para no cambiar)"
vehicle.vin            → "VIN"
vehicle.username       → "Username" / "Usuario"
vehicle.locale         → "Locale" / "Región"
vehicle.password       → "Password" / "Contraseña"
vehicle.pushUrl        → "Push URL"
vehicle.location       → "Location" / "Ubicación"
vehicle.noLocation     → "No location data" / "Sin datos de ubicación"
vehicle.edit           → "Edit" / "Editar"
vehicle.delete         → "Delete" / "Eliminar"
vehicle.confirmDelete  → "Delete \"{{name}}\"?" / "¿Eliminar \"{{name}}\"?"
```

## Risks / Trade-offs

**[Risk] Translation files not found (404) → blank strings**
Mitigation: `i18next-http-backend` logs a warning; i18next falls back to the key name (visible but not broken). CI/build-time check can catch missing files.

**[Risk] Missing translation key → key rendered as-is**
Mitigation: i18next falls back to the `fallbackLng` (`en`) translation file, so a missing Spanish key shows English text — graceful degradation. A complete key audit at build time would catch gaps.

**[Risk] Playwright tests break if localStorage setup runs after app init**
Mitigation: Set `localStorage` before any page navigation in the fixture. The `storageState` pattern in Playwright guarantees this ordering.

**[Risk] `"Cargando zonas…"` in MapPage is Spanish but existing tests may rely on it**
Mitigation: Grep E2E tests for this string before removing it. None of the current test files reference it (they test auth and vehicle CRUD only).

## Migration Plan

1. Install 4 npm packages.
2. Add `frontend/src/i18n.ts` and import it in `main.tsx` before `<App>` renders.
3. Add translation files to `frontend/public/locales/`.
4. Update each component file to use `useTranslation()` — no behaviour changes.
5. Update Playwright fixtures to set `i18nextLng=en` in localStorage.
6. Verify with `npm run lint` and `npx playwright test` — tests should pass unchanged.

Rollback: remove the i18n import from `main.tsx` and revert component files. No database or API changes to undo.
