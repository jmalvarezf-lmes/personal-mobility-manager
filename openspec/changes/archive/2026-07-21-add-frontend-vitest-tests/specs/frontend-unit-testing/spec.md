## ADDED Requirements

### Requirement: Vitest is configured as the frontend unit-test runner
The frontend SHALL have a Vitest `test` configuration (merged into `frontend/vite.config.ts` via `defineConfig` from `vitest/config`) using the `jsdom` environment. `frontend/package.json` SHALL expose a `test` script that runs `vitest run`.

#### Scenario: Test script runs the suite once and exits
- **WHEN** `pnpm test` is run
- **THEN** Vitest executes all `*.test.ts`/`*.test.tsx` files once and exits with code 0 if all pass, non-zero if any fail

#### Scenario: DOM APIs are available to component tests
- **WHEN** a test file renders a React component via Testing Library
- **THEN** `jsdom`-provided DOM APIs (`document`, `window`, event dispatch) are available without a real browser

### Requirement: A shared test render helper wraps required providers
`frontend/src/test/render.tsx` SHALL export a `renderWithProviders` helper that wraps a component under test with the providers it needs to render without throwing (`I18nextProvider` using a synchronous test i18n instance, and `AuthProvider`/router context where the component under test requires them).

#### Scenario: Component using useTranslation renders without a provider error
- **WHEN** a component that calls `useTranslation()` is rendered via `renderWithProviders`
- **THEN** it renders successfully and displays the real English strings from `en/translation.json`

#### Scenario: Component using useAuth renders without a provider error
- **WHEN** a component that (directly or via a child like `Nav`) calls `useAuth()` is rendered via `renderWithProviders`
- **THEN** it renders successfully instead of throwing "useAuth must be used inside <AuthProvider>"

### Requirement: Test i18n instance uses real translation strings without network calls
`frontend/src/test/i18n.ts` SHALL initialize a dedicated i18next instance via `initReactI18next`, loading `en/translation.json` directly as an imported resource bundle rather than through `i18next-http-backend`.

#### Scenario: No network request during a component test
- **WHEN** a component test renders a component that calls `useTranslation()`
- **THEN** no HTTP request is made to load translation resources

#### Scenario: Rendered strings match production English copy
- **WHEN** a component renders a translated string in a test
- **THEN** the rendered text matches the value in `frontend/public/locales/en/translation.json` for that key

### Requirement: Pure-logic modules have unit test coverage
`src/utils/timezone.ts`, `src/api/*.ts`, and `src/components/notificationChannels/registry.ts` SHALL each have a colocated `*.test.ts` file exercising their exported functions/values, including error and fallback branches.

#### Scenario: Timezone resolution and formatting behavior is covered
- **WHEN** `src/utils/timezone.test.ts` runs
- **THEN** it asserts the preference/browser-detected/UTC resolution cascade, the DST-aware abbreviation switch (CET/CEST) for `Europe/Madrid`, and the unrecognized-zone fallback to UTC formatting

#### Scenario: API request functions handle non-OK responses
- **WHEN** an `src/api/*.test.ts` file exercises a request function against a mocked `fetch` returning a non-OK status
- **THEN** the function throws an `Error`, and for functions that read a response body on failure, the thrown message includes that body's text

#### Scenario: API request functions construct correct URLs and bodies
- **WHEN** an `src/api/*.test.ts` file exercises a request function that takes parameters (e.g. `getVehicleLocationHistory`'s `limit`/`offset`, or a POST body)
- **THEN** the mocked `fetch` is asserted to have been called with the expected URL (including query string) and, for mutating requests, the expected JSON-serialized body

### Requirement: Interactive components with documented regressions have component-level test coverage
`PreferencesPage`'s timezone combobox, `VehicleCard`'s ambient-label render states, and `AmbientLabelIcon` SHALL each have a colocated `*.test.tsx` file using Testing Library to simulate user interaction and assert rendered output.

#### Scenario: Timezone combobox live-filters as the user types
- **WHEN** a user types a partial zone name into the `PreferencesPage` timezone combobox in a test
- **THEN** the filtered option list updates to show only matching timezone options, without requiring the dropdown to be reopened

#### Scenario: Enter in the timezone combobox never submits the form
- **WHEN** a user presses Enter while the timezone combobox is focused, with the dropdown open and at least one matching option
- **THEN** the top matching option is committed as the input value, and no form submission (no save request) is triggered

#### Scenario: VehicleCard renders each ambient-label state
- **WHEN** `VehicleCard` is rendered with a vehicle that has an ambient label, with a vehicle that has none, and with a vehicle whose ambient label is `null`
- **THEN** the icon, the "no label" indicator, and no ambient-label element (respectively) are rendered for each case
