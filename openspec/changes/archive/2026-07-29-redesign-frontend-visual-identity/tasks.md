## 1. Brand tokens and primitives

- [x] 1.1 Add brand color tokens (teal/green accent + existing blue/navy) as Tailwind `@theme` custom properties in `frontend/src/index.css`
- [x] 1.2 Create `frontend/src/components/ui/Button.tsx` (primary/secondary variants)
- [x] 1.3 Create `frontend/src/components/ui/Card.tsx`
- [x] 1.4 Create `frontend/src/components/ui/Input.tsx` (text/number, reusable for `<select>` styling)
- [x] 1.5 Create `frontend/src/components/ui/PageHeader.tsx` (title + optional action slot)
- [x] 1.6 Add unit tests for the primitives (variant rendering, class application) under `frontend/src/components/ui/*.test.tsx`

## 2. Nav

- [x] 2.1 Wrap the nav title/logo in `Nav.tsx` with `<Link to="/">`
- [x] 2.2 Migrate `Nav.tsx`'s auth control and account dropdown to the `Button`/primitive styling
- [x] 2.3 Run `frontend/e2e/nav.spec.ts` and confirm the outside-click test (which clicks the title text) still passes with the title as a link

## 3. Landing page content

- [x] 3.1 Add `page.landing.*` copy keys (hero headline, subcopy, feature highlights for track/park/notify) to `frontend/public/locales/en/translation.json` and `es/translation.json`
- [x] 3.2 Build the hero section in `LandingPage.tsx` (headline, subcopy, login CTA) using the new primitives
- [x] 3.3 Build the three-feature section in `LandingPage.tsx` mirroring the logo's track/park/notify tagline
- [x] 3.4 Update `frontend/e2e` landing-page assertions (if any target the old bare-title markup) to match the new content — no existing e2e spec targets the old landing markup (confirmed via grep across `e2e/*.spec.ts`); nothing to update

## 4. My Vehicles page

- [x] 4.1 Migrate `MyVehiclesPage.tsx` header/layout to `PageHeader`/`Card`/`Button`
- [x] 4.2 Migrate `VehicleCard.tsx` to `Card`/`Button` primitives
- [x] 4.3 Migrate `AddVehicleModal.tsx` and `EditVehicleModal.tsx` to `Input`/`Button` primitives
- [x] 4.4 Run `frontend/e2e/my-vehicles.spec.ts` and `vehicle-location-history-modal.spec.ts`, confirm passing

## 5. Preferences page

- [x] 5.1 Migrate `PreferencesPage.tsx` form fields to `Input`/`PageHeader`/`Button` primitives
- [x] 5.2 Run `frontend/e2e/preferences.spec.ts`, confirm passing

## 6. SER Providers page

- [x] 6.1 Migrate `SerProvidersPage.tsx` and `SerProviderRow.tsx` to `Card`/`Button` primitives
- [x] 6.2 Migrate `ConnectSerProviderModal.tsx` to `Input`/`Button` primitives
- [x] 6.3 Run `frontend/e2e/ser-providers.spec.ts` and `ser-parking-exemption.spec.ts`, confirm passing

## 7. Notification Channels page

- [x] 7.1 Migrate `NotificationChannelsPage.tsx` and `NotificationChannelRow.tsx` to `Card`/`Button` primitives
- [x] 7.2 Run `frontend/e2e/notification-channels.spec.ts`, confirm passing

## 8. Final verification

- [x] 8.1 Run `pnpm test` (Vitest) across the frontend, confirm all unit tests pass — 23 files / 132 tests pass
- [x] 8.2 Run the full Playwright e2e suite (`npx playwright test`), confirm all specs pass including `map.spec.ts` — 69/69 non-map specs pass; `map.spec.ts`'s 4 tests fail identically on the pre-change baseline (no backend running at `localhost:8000` in this environment — confirmed via `git stash` A/B comparison), unrelated to this change
- [~] 8.3 Manually verify in a running browser: clicking the nav title from `/map`, `/my-vehicles`, `/preferences` returns to `/`; landing page reads correctly for both a logged-out and a logged-in session — PARTIAL: verified with `pnpm dev` + chrome-devtools against `/` (hero, feature cards, EN/ES locales) and confirmed the nav title renders as a real `<Link>` and SPA-navigates correctly; found and fixed a real bug (nav login `Button` had no `whitespace-nowrap`, wrapped to 4 lines in Spanish). Could not verify `/my-vehicles`, `/preferences`, or a logged-in session — no backend running in this sandbox, and those routes require live auth/data
- [x] 8.4 Confirm no unused-asset lint/build warnings introduced (e.g. `hero.png` remains genuinely unused and is not accidentally imported) — `eslint`, `tsc --noEmit`, and `vite build` all clean; confirmed via grep that `hero.png` and `icons.svg` are still unreferenced in `src/`
