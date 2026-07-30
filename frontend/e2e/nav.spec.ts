import { expect } from "@playwright/test";
import { test as base } from "./fixtures/coverage";
import { MOCK_USER, test } from "./fixtures/auth";
import { NavPage } from "./pages/NavPage";

// ---------------------------------------------------------------------------
// Account dropdown
// ---------------------------------------------------------------------------

test.describe("Account dropdown", () => {
  test("opens on trigger click revealing My Vehicles, Preferences, and Logout", async ({
    page,
  }) => {
    await page.goto("/");
    const nav = new NavPage(page, MOCK_USER.email);

    await expect(nav.accountTrigger).toHaveAttribute("aria-expanded", "false");
    await nav.open();

    await expect(nav.accountTrigger).toHaveAttribute("aria-expanded", "true");
    await expect(nav.myVehiclesLink).toBeVisible();
    await expect(nav.preferencesLink).toBeVisible();
    await expect(nav.logoutButton).toBeVisible();
  });

  test("closes when selecting a menu item", async ({ page }) => {
    await page.goto("/");
    const nav = new NavPage(page, MOCK_USER.email);
    await nav.open();

    await nav.preferencesLink.click();
    await expect(nav.menu).not.toBeVisible();
  });

  test("closes on outside click", async ({ page }) => {
    await page.goto("/");
    const nav = new NavPage(page, MOCK_USER.email);
    await nav.open();
    await expect(nav.menu).toBeVisible();

    await page.getByText("Personal Mobility Manager").first().click();
    await expect(nav.menu).not.toBeVisible();
  });

  base("logged-out visitor sees no account trigger, only the Google login button", async ({
    page,
  }) => {
    await page.route("**/api/auth/me", (route) =>
      route.fulfill({ status: 401 }),
    );
    await page.goto("/");
    const nav = new NavPage(page, MOCK_USER.email);

    await expect(nav.accountTrigger).not.toBeVisible();
    // Scoped to the nav landmark: the redesigned landing page also renders
    // its own "Login with Google" CTA in the hero section, so an unscoped
    // locator would match two links.
    await expect(
      page.getByRole("navigation").getByRole("link", { name: /login with google/i }),
    ).toBeVisible();
  });
});
