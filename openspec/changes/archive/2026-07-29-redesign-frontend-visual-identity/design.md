## Context

The app's Tailwind styling is functionally consistent (every page follows the same `<Nav /> + <h1> + content` skeleton) but visually generic: default `gray-800`/`blue-600` palette, no brand colors, no shared component layer. The same class fragments (`bg-blue-600 hover:bg-blue-700` for primary buttons, `rounded border border-gray-300 px-3 py-2 text-sm` for inputs, `rounded border border-gray-200 bg-white p-4 shadow-sm` for cards) are duplicated inline across at least 8 files: `Nav.tsx`, `PreferencesPage.tsx`, `VehicleCard.tsx`, `SerProviderRow.tsx`, `AddVehicleModal.tsx`, `EditVehicleModal.tsx`, `ConnectSerProviderModal.tsx`, `NotificationChannelRow.tsx`.

`frontend/public/logo.png` is a real designed brand mark (gradient blue→teal "P" pin/car/signal icon with a "track / park / notify" tagline) that the running app never renders — it's referenced only from the repo's `README.md`. Sampling the logo's pixels gives concrete brand colors:

| Element | Sampled | Notes |
|---|---|---|
| Pin top (accent) | `#37CFAD` | New — no equivalent in current palette |
| Pin bottom | `#1767CC` | Close to Tailwind `blue-600` (`#2563EB`), already in use |
| Wordmark / car icon ink | `#1E273E` | Nearly identical to Tailwind `slate-800` (`#1E293B`), already in use as `text-gray-800` |

So adopting the brand is smaller than a full repaint: keep the existing blue/navy (already close), add one teal/green accent, and use a blue→teal gradient for hero/CTA moments only.

`src/assets/hero.png` (a small isometric icon) is unused; since `logo.png` already carries the brand mark, it is not used in the hero section — avoids two competing icon marks on one page.

`public/icons.svg` contains unused `bluesky`/`discord`/`github`/`x`/`documentation` icons, confirmed leftover (not real accounts) — excluded from any footer.

## Goals / Non-Goals

**Goals:**
- Give `/` real content: hero pitch, three-feature section (track / park / notify), login CTA.
- Make the shared `Nav` title a link to `/`.
- Establish brand-based Tailwind theme tokens and a small primitive component set (`Button`, `Card`, `Input`, `PageHeader`).
- Migrate `Nav` and all authenticated pages/modals to the new primitives so the whole app reads as one visual system.

**Non-Goals:**
- No new routes, no auth/redirect behavior changes (`/` still serves both authenticated and unauthenticated users per the existing `landing-page` spec).
- No backend/API changes.
- No functional changes to forms/pages beyond swapping styling — field behavior, validation, and data flow stay identical.
- No footer social links (leftover assets, explicitly dropped).
- No full design-token system (spacing scale, dark mode, etc.) beyond color tokens + the four primitives — kept to what this change's pages actually need.

## Decisions

**1. Tailwind theme tokens via CSS custom properties in `index.css`, not a `tailwind.config` rewrite.**
This project uses Tailwind v4's CSS-first `@theme` configuration (see `@import "tailwindcss"` in `index.css`, no `tailwind.config.js`). Add brand colors as `@theme` tokens (e.g. `--color-brand-teal: #14b8a6`-range, `--color-brand-blue: #2563eb`, kept as Tailwind's own `blue-600`) so they're usable as ordinary utility classes (`bg-brand-teal`, `text-brand-blue`) without a build config change.

**2. Four primitives, not a full component library.**
`Button` (primary/secondary variants), `Card`, `Input` (text/number, shares styling with `select`), `PageHeader` (title + optional action slot, replacing the repeated `<h1> + action button` header pattern in every page). This covers every duplicated fragment found in the audit without over-engineering a design system for a 4-route app. New shared components live under `frontend/src/components/ui/`.

**3. Landing page content structure mirrors the logo's own tagline.**
Hero (headline + subcopy + login CTA) → three feature cards labeled from the existing brand tagline: track (map/location), park (SER zone ticket automation), notify (notification channels) → optional lightweight "how it works" steps. Copy goes through i18n (`page.landing.*` keys in both `en`/`es` translation files), consistent with how every other page is localized.

**4. `Nav` title becomes `<Link to="/">` wrapping the existing title text/logo mark, not a new component.**
Smallest change that satisfies "always takes to home." Since `Nav` is shared across every route, this one edit fixes it everywhere at once.

**5. Page-by-page primitive migration, landing/Nav first.**
`Nav` and `LandingPage` first (most visible, no dependents), then `MyVehiclesPage`/`VehicleCard`, then `PreferencesPage`, then `SerProvidersPage`/`SerProviderRow`, then `NotificationChannelsPage`/`NotificationChannelRow`, then the three modals. Each page swap is independently shippable and testable — avoids one giant diff touching everything at once.

## Risks / Trade-offs

- **[Risk]** `frontend/e2e/nav.spec.ts` clicks the nav title text (`page.getByText("Personal Mobility Manager").first().click()`) to test the account dropdown's outside-click behavior. Making the title a `Link to="/"` changes that element into a navigation trigger. → **Mitigation**: the test already runs on `/`, so navigating to `/` is a no-op route change; re-run `nav.spec.ts` after the change to confirm the dropdown-close assertion still holds.
- **[Risk]** Migrating ~8 files to shared primitives in one broad change risks visual regressions in existing Playwright specs (`preferences.spec.ts`, `my-vehicles.spec.ts`, `ser-providers.spec.ts`, `notification-channels.spec.ts`) that use `getByRole`/`getByLabel` selectors. → **Mitigation**: primitives preserve semantic HTML (`<button>`, `<input>`, `<label htmlFor>`) and existing `aria-*`/`role` attributes; only class names and DOM wrapper structure change. Run the full e2e + vitest suite after each page's migration, not just at the end.
- **[Risk]** Scope creep: "modernize everything" could balloon into unrelated refactors. → **Mitigation**: tasks.md scopes each page to a pure styling swap; no logic, state, or API changes bundled in.
- **[Trade-off]** Introducing `frontend/src/components/ui/` primitives now, for a 4-page app, is more upfront work than inline restyling (Option B considered and rejected during exploration) — accepted because every page already duplicates the same classes today, so the maintenance cost of *not* centralizing them has already shown up once and will recur.

## Migration Plan

No deployment/data migration — frontend-only, no schema or API changes. Ship as a single PR once all pages are migrated and the full frontend test suite passes: `pnpm test` (Vitest unit tests) and `npx playwright test` (e2e). Rollback is a normal `git revert` — no runtime state to reconcile.
