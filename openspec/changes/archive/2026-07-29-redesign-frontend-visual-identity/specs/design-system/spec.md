## ADDED Requirements

### Requirement: Brand color tokens are defined once and reused
The system SHALL define brand color tokens (a teal/green accent alongside the existing blue and navy) as Tailwind `@theme` custom properties in `frontend/src/index.css`, exposed as utility classes (e.g. `bg-brand-teal`, `text-brand-blue`) usable anywhere in the frontend without redefining raw hex values inline.

#### Scenario: Brand accent color is available as a utility class
- **WHEN** a component uses the brand accent utility class (e.g. `bg-brand-teal`)
- **THEN** it renders using the accent color sampled from `frontend/public/logo.png`, without a locally hardcoded hex value in that component

### Requirement: Shared primitive UI components exist for buttons, cards, inputs, and page headers
The system SHALL provide reusable `Button`, `Card`, `Input`, and `PageHeader` components under `frontend/src/components/ui/` that encapsulate the app's visual styling (color, spacing, border radius, shadow) so pages do not redefine these styles inline.

#### Scenario: Button primitive supports primary and secondary variants
- **WHEN** a `Button` is rendered with the primary variant
- **THEN** it uses the brand color tokens for its background
- **WHEN** a `Button` is rendered with the secondary variant
- **THEN** it uses a neutral background distinct from the primary variant

#### Scenario: Card, Input, and PageHeader primitives render with consistent styling
- **WHEN** any page renders a `Card`, `Input`, or `PageHeader`
- **THEN** the rendered element uses the shared primitive component's styling rather than page-local Tailwind classes

### Requirement: Nav and authenticated pages adopt the shared primitives
The system SHALL render `Nav`, `LandingPage`, `MyVehiclesPage`, `VehicleCard`, `PreferencesPage`, `SerProvidersPage`, `SerProviderRow`, `NotificationChannelsPage`, `NotificationChannelRow`, `AddVehicleModal`, `EditVehicleModal`, and `ConnectSerProviderModal` using the shared primitive components instead of page-local duplicated Tailwind class strings, with no change to each page's existing functional behavior (routing, validation, data submission).

#### Scenario: Existing page behavior is unchanged after primitive adoption
- **WHEN** a page migrated to the shared primitives is exercised through its existing test suite (unit or e2e)
- **THEN** all previously passing assertions about behavior (form submission, navigation, role/label-based selectors) continue to pass
