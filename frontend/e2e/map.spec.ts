import { expect, test } from "@playwright/test";

test.describe("Map page", () => {
  test("map container is present on load", async ({ page }) => {
    await page.goto("/");
    await expect(page.locator(".leaflet-container")).toBeVisible();
  });

  test("zone markers appear after data loads", async ({ page }) => {
    const zonesResponsePromise = page.waitForResponse(
      (resp) => resp.url().includes("/api/parking/ser-zones") && resp.status() === 200
    );

    await page.goto("/");
    await zonesResponsePromise;

    await expect(page.locator("path.leaflet-interactive").first()).toBeVisible({
      timeout: 10_000,
    });
  });

  test("tooltip shows zone details on marker interaction", async ({ page }) => {
    const zonesResponsePromise = page.waitForResponse(
      (resp) => resp.url().includes("/api/parking/ser-zones") && resp.status() === 200
    );

    await page.goto("/");
    await zonesResponsePromise;

    const firstMarker = page.locator("path.leaflet-interactive").first();
    await firstMarker.waitFor({ timeout: 10_000 });
    await firstMarker.hover();

    const tooltip = page.locator(".leaflet-tooltip");
    await expect(tooltip).toBeVisible({ timeout: 5_000 });
    await expect(tooltip).toContainText(/\d+/);
  });
});
