import { expect, test } from "./fixtures/auth";

test.describe("Map page", () => {
  test("map container is present on load", async ({ page }) => {
    await page.goto("/map");
    await expect(page.locator(".leaflet-container")).toBeVisible({ timeout: 15000 });
  });

  test("zone polygons appear after data loads", async ({ page }) => {
    const zonesResponsePromise = page.waitForResponse(
      (resp) =>
        resp.url().includes("/api/parking/ser-zones") && resp.status() === 200,
    );

    await page.goto("/map");
    const zonesResponse = await zonesResponsePromise;
    const data = (await zonesResponse.json()) as {
      zones: unknown[];
      frontiers: unknown[];
    };

    expect(data.zones.length).toBeGreaterThan(0);

    // react-leaflet's GeoJSON layer renders each zone as an SVG <path>
    // element inside the overlay pane. Zone (street-band) polygons are
    // non-interactive — pure colour fills, with mouse events passing
    // through to the frontier layer beneath (see ZoneMap.tsx) — so they
    // don't carry the "leaflet-interactive" class; exclude the frontier
    // paths instead to isolate them.
    await expect(
      page.locator(".leaflet-overlay-pane path:not(.zone-frontier)"),
    ).not.toHaveCount(0, { timeout: 10_000 });
  });

  test("frontier polygons appear after data loads", async ({ page }) => {
    const zonesResponsePromise = page.waitForResponse(
      (resp) =>
        resp.url().includes("/api/parking/ser-zones") && resp.status() === 200,
    );

    await page.goto("/map");
    const zonesResponse = await zonesResponsePromise;
    const data = (await zonesResponse.json()) as {
      zones: unknown[];
      frontiers: unknown[];
    };

    expect(data.frontiers.length).toBeGreaterThan(0);

    // Frontier polygons are rendered as a separate react-leaflet GeoJSON
    // layer with a fixed "zone-frontier" className (see ZoneMap.tsx),
    // distinguishing them from the precise zone polygons in the DOM.
    await expect(
      page.locator(".leaflet-overlay-pane path.zone-frontier"),
    ).not.toHaveCount(0, { timeout: 10_000 });
  });

  test("tooltip shows zone details on polygon interaction", async ({ page }) => {
    const zonesResponsePromise = page.waitForResponse(
      (resp) =>
        resp.url().includes("/api/parking/ser-zones") && resp.status() === 200,
    );

    await page.goto("/map");
    await zonesResponsePromise;

    // Zone (street-band) polygons are non-interactive colour fills — mouse
    // events pass through to the frontier layer beneath, which carries the
    // single unified tooltip (zone code + neighbourhood + spot counts
    // grouped by colour; see ZoneMap.tsx). So the frontier polygon is the
    // only interactive target on the map.
    const polygon = page
      .locator(".leaflet-overlay-pane path.leaflet-interactive.zone-frontier")
      .first();
    await expect(polygon).toBeVisible({ timeout: 10_000 });

    await polygon.hover();

    const tooltip = page.locator(".leaflet-tooltip");
    await expect(tooltip).toBeVisible({ timeout: 5_000 });
    // Tooltip shows the zone number and neighbourhood name — no street
    // names (see design.md D9 / osm-zone-map spec).
    await expect(tooltip).toContainText(/\d+/);
  });
});
