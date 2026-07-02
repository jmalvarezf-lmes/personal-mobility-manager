### Requirement: Browser language is detected automatically on load
The system SHALL detect the user's preferred language from the browser (`navigator.languages` / `navigator.language`) on app startup. The detected language SHALL be resolved to one of the supported locales (`en`, `es`). If the detected language does not match any supported locale, the system SHALL fall back to `en`. The resolved language SHALL be stored in `localStorage` so subsequent visits skip detection.

#### Scenario: Spanish browser loads in Spanish
- **WHEN** the browser's preferred language is `es` or `es-ES`
- **THEN** the app renders all UI strings in Spanish

#### Scenario: English browser loads in English
- **WHEN** the browser's preferred language is `en`, `en-US`, or `en-GB`
- **THEN** the app renders all UI strings in English

#### Scenario: Unsupported language falls back to English
- **WHEN** the browser's preferred language is not `en` or `es`
- **THEN** the app renders all UI strings in English

#### Scenario: Returning user uses stored preference
- **WHEN** `localStorage` contains a previously saved language choice
- **THEN** the app loads in that language without re-running browser detection

---

### Requirement: User can switch language via Nav selector
The system SHALL render a language selector `<select>` element in the navigation bar. The selector SHALL display the currently active language pre-selected. Changing the selector value SHALL immediately switch all UI strings to the chosen language and persist the choice to `localStorage`.

#### Scenario: Selector shows detected language pre-selected
- **WHEN** the app loads with browser language `es`
- **THEN** the language selector shows `es` as the selected option

#### Scenario: User switches language
- **WHEN** the user changes the language selector from `en` to `es`
- **THEN** all visible UI strings switch to Spanish immediately without a page reload
- **THEN** `localStorage` stores `es` as the preferred language

#### Scenario: Language preference persists across navigation
- **WHEN** the user switches to Spanish and then navigates to another route
- **THEN** the new route also renders in Spanish

---

### Requirement: All UI strings are externalised into translation files
The system SHALL provide translation files for each supported locale at `frontend/public/locales/{lng}/translation.json`. All hardcoded UI strings in Nav, LandingPage, MapPage, MyVehiclesPage, AddVehicleModal, EditVehicleModal, and VehicleCard SHALL be replaced by calls to the i18next `t()` function. Backend API error messages are exempt and may remain in English.

#### Scenario: English translation file covers all keys
- **WHEN** the active language is `en`
- **THEN** every UI string resolves to a non-empty English value

#### Scenario: Spanish translation file covers all keys
- **WHEN** the active language is `es`
- **THEN** every UI string resolves to a non-empty Spanish value

---

### Requirement: Playwright tests always run in English
The system SHALL configure E2E test fixtures to force the active language to `en` before each test, regardless of the test runner environment's browser locale. This SHALL be done by setting `lng=en` in `localStorage` during test setup.

#### Scenario: E2E tests run in English regardless of browser locale
- **WHEN** Playwright tests execute
- **THEN** the app renders in English for all test scenarios
