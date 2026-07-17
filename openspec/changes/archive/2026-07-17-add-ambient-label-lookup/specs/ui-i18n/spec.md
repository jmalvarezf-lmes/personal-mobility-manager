## MODIFIED Requirements

### Requirement: All UI strings are externalised into translation files
The system SHALL provide translation files for each supported locale at `frontend/public/locales/{lng}/translation.json`. All hardcoded UI strings in Nav, LandingPage, MapPage, MyVehiclesPage, AddVehicleModal, EditVehicleModal, VehicleCard, and AmbientLabelIcon SHALL be replaced by calls to the i18next `t()` function. Backend API error messages are exempt and may remain in English.

#### Scenario: English translation file covers all keys
- **WHEN** the active language is `en`
- **THEN** every UI string resolves to a non-empty English value

#### Scenario: Spanish translation file covers all keys
- **WHEN** the active language is `es`
- **THEN** every UI string resolves to a non-empty Spanish value
