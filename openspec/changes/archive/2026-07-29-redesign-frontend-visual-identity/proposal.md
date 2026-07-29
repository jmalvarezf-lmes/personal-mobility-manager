## Why

The frontend is functional but says nothing about the product: `/` renders only a bare title with no pitch, no features, no images, and the shared nav title is plain text instead of a link home. Meanwhile the project already has a real brand identity — `frontend/public/logo.png` (a designed mark with a "track / park / notify" tagline) — that the running app never shows. Every page also hand-rolls the same Tailwind class strings for buttons, inputs, and cards with no shared source of truth, so "make it modern" would otherwise mean copy-pasting new styles into eight-plus files by hand.

## What Changes

- Nav title (`Nav.tsx`) becomes a `Link` to `/`, rendered on every page since `Nav` is shared app-wide.
- `/` (landing page) gains real content: a hero section stating the product's value proposition, a three-part feature section mirroring the logo's "track / park / notify" tagline, and a prominent login CTA. It remains open to both unauthenticated and authenticated users — no redirect — matching the existing `landing-page` spec's intent, just with substance instead of a bare `<h1>`.
- New shared design system: Tailwind theme tokens for the brand palette (adds the logo's teal/green accent alongside the existing blue/navy, which are already close to the brand) plus primitive components (`Button`, `Card`, `Input`, `PageHeader`) extracted from the repeated inline class patterns.
- The new primitives are adopted by `Nav`, `LandingPage`, and the authenticated pages and modals (My Vehicles, Preferences, SER Providers, Notification Channels, and their modals) so the whole app shares one visual language. This is a visual/implementation change only — no routing, auth, or data-flow behavior changes on those pages.
- Explicitly out of scope: the unused social icons in `public/icons.svg` (bluesky/discord/github/x) are leftover and are not wired into any footer.

## Capabilities

### New Capabilities
- `design-system`: Tailwind theme tokens for the brand palette and a small set of shared primitive UI components (`Button`, `Card`, `Input`, `PageHeader`) used consistently across the app instead of per-file inline styling.

### Modified Capabilities
- `landing-page`: the "Landing page is the app entry point at /" requirement changes from displaying only the app title to rendering real marketing content (hero copy, feature highlights, login CTA); the "Navigation bar is shared across pages" requirement changes so the app title/logo is a clickable link to `/`.

## Impact

Frontend-only change. Affected areas:
- `frontend/src/components/Nav.tsx` — title becomes a link.
- `frontend/src/pages/LandingPage.tsx` — new hero/feature content.
- New shared primitives under `frontend/src/components/ui/` (or similar) and Tailwind theme configuration.
- `frontend/src/pages/MyVehiclesPage.tsx`, `PreferencesPage.tsx`, `SerProvidersPage.tsx`, `NotificationChannelsPage.tsx`, `VehicleCard.tsx`, `AddVehicleModal.tsx`, `EditVehicleModal.tsx`, `ConnectSerProviderModal.tsx`, `SerProviderRow.tsx`, `notificationChannels/NotificationChannelRow.tsx` — adopt shared primitives in place of inline duplicated classes.
- `frontend/public/locales/en/translation.json` and `es/translation.json` — new landing page copy keys.
- No backend, API, or database changes.
