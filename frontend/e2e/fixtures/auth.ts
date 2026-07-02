import { test as base } from "@playwright/test";

export const MOCK_USER = {
  id: "00000000-0000-0000-0000-000000000001",
  email: "test@example.com",
  display_name: "Test User",
};

/**
 * Extends `test` so that `page` always has /api/auth/me mocked to return
 * MOCK_USER. Import this `test` in any spec that requires an authenticated
 * session. For unauthenticated scenarios, import from @playwright/test directly.
 */
export const test = base.extend({
  page: async ({ page }, use) => {
    await page.route("**/api/auth/me", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(MOCK_USER),
      }),
    );
    await page.addInitScript(() => {
      localStorage.setItem("i18nextLng", "en");
    });
    await use(page);
  },
});

export { expect } from "@playwright/test";
