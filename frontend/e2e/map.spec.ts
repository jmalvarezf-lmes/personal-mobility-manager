import { expect, test } from "@playwright/test";

// Retrieves the Leaflet map instance from the MapContainer's React ref
// by walking the fiber hook chain of the .leaflet-container element.
function leafletMapFromFiber(): { x: number; y: number } | null {
  const container = document.querySelector(".leaflet-container");
  if (!container) return null;
  const fiberKey = Object.keys(container).find((k) =>
    k.startsWith("__reactFiber"),
  );
  if (!fiberKey) return null;
  // The map ref sits in hook[2] of the MapContainer fiber (parent of the container div)
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  let hook = (container as any)[fiberKey].return?.memoizedState;
  for (let i = 0; i < 2; i++) hook = hook?.next;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const map = hook?.memoizedState?.current;
  if (!map?.eachLayer) return null;
  let pos: { x: number; y: number } | null = null;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  map.eachLayer((layer: any) => {
    if (pos || typeof layer.getLatLng !== "function") return;
    const pt = map.latLngToContainerPoint(layer.getLatLng());
    pos = { x: Math.round(pt.x), y: Math.round(pt.y) };
  });
  return pos;
}

test.describe("Map page", () => {
  test("map container is present on load", async ({ page }) => {
    await page.goto("/");
    await expect(page.locator(".leaflet-container")).toBeVisible();
  });

  test("zone markers appear after data loads", async ({ page }) => {
    const zonesResponsePromise = page.waitForResponse(
      (resp) =>
        resp.url().includes("/api/parking/ser-zones") && resp.status() === 200,
    );

    await page.goto("/");
    const zonesResponse = await zonesResponsePromise;
    const data = (await zonesResponse.json()) as { zones: unknown[] };

    expect(data.zones.length).toBeGreaterThan(0);

    // CircleMarkers use canvas renderer — verify the canvas is painted
    await expect(page.locator("canvas.leaflet-zoom-animated")).toBeVisible({
      timeout: 10_000,
    });
  });

  test("tooltip shows zone details on marker interaction", async ({ page }) => {
    const zonesResponsePromise = page.waitForResponse(
      (resp) =>
        resp.url().includes("/api/parking/ser-zones") && resp.status() === 200,
    );

    await page.goto("/");
    await zonesResponsePromise;

    await expect(page.locator("canvas.leaflet-zoom-animated")).toBeVisible({
      timeout: 10_000,
    });

    // Get viewport pixel coords of the first CircleMarker via the Leaflet map instance
    const markerPos = await page.evaluate(leafletMapFromFiber);
    expect(markerPos).not.toBeNull();

    await page.mouse.move(markerPos!.x, markerPos!.y);

    const tooltip = page.locator(".leaflet-tooltip");
    await expect(tooltip).toBeVisible({ timeout: 5_000 });
    await expect(tooltip).toContainText(/\d+/);
  });
});
