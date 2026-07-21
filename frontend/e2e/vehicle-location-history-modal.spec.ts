import { expect, type Page } from "@playwright/test";
import { test } from "./fixtures/auth";
import { MyVehiclesPage } from "./pages/MyVehiclesPage";

// `Intl`'s `timeZoneName: 'short'` abbreviation is locale-dependent CLDR
// data — for many locales (including plain "en"/"en-US", Chromium's
// default), most IANA zones (Europe/Madrid included) resolve to a generic
// "GMT+1"/"GMT+2" offset rather than "CET"/"CEST". This is a genuine
// browser/ICU behavior, not a bug in formatInTimezone — see the apply-phase
// report. "en-GB" reliably carries the named abbreviation for this zone, so
// it's pinned here to test the designed behavior deterministically.
test.use({ locale: "en-GB" });

// ---------------------------------------------------------------------------
// Mock data
// ---------------------------------------------------------------------------

const TOYOTA_ID = "00000000-0000-0000-0000-000000000010";

const MOCK_VEHICLES = [
  {
    vehicle_id: TOYOTA_ID,
    brand: "toyota",
    display_name: "My Toyota",
    vin: "JTDBF3EJ8A3045678",
    location: {
      latitude: 40.4168,
      longitude: -3.7038,
      recorded_at: "2026-07-15T13:00:00Z",
    },
    ambient_label: null,
  },
];

const DEFAULT_PREFERENCES = {
  default_ticket_duration_minutes: 60,
  auto_create_ticket: false,
  preferred_notification_channel: null as string | null,
  notification_language: null as string | null,
  timezone: null as string | null,
};

/**
 * Wires up the vehicle list + preferences + location-history routes needed
 * to open VehicleLocationHistoryModal for the single mocked Toyota.
 */
async function mockApis(
  page: Page,
  locations: { latitude: number; longitude: number; recorded_at: string }[],
  preferencesTimezone: string | null = null,
) {
  await page.route("**/api/config", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ osm_tile_url: null }),
    }),
  );

  await page.route("**/api/parking/ser-zones**", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ city: "madrid", zones: [] }),
    }),
  );

  await page.route("**/api/vehicles", (route, request) => {
    if (request.method() === "GET") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(MOCK_VEHICLES),
      });
    }
    return route.continue();
  });

  await page.route("**/api/preferences", (route, request) => {
    if (request.method() === "GET") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ ...DEFAULT_PREFERENCES, timezone: preferencesTimezone }),
      });
    }
    return route.continue();
  });

  await page.route(`**/api/vehicles/${TOYOTA_ID}/locations**`, (route, request) => {
    if (request.method() === "GET") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ items: locations, has_more: false }),
      });
    }
    return route.continue();
  });
}

test.describe("VehicleLocationHistoryModal — resolved timezone display", () => {
  test("list row shows the resolved timezone and abbreviation, not raw UTC", async ({
    page,
  }) => {
    await mockApis(
      page,
      [{ latitude: 40.4168, longitude: -3.7038, recorded_at: "2026-07-15T13:00:00Z" }],
      "Europe/Madrid",
    );
    const myVehicles = new MyVehiclesPage(page);
    await myVehicles.goto();
    await myVehicles.openHistoryModal("My Toyota");

    // 13:00 UTC in July is 15:00 in Madrid (CEST, UTC+2).
    await expect(myVehicles.historyModal).toContainText("15:00");
    await expect(myVehicles.historyModal).toContainText("CEST");
    await expect(myVehicles.historyModal).not.toContainText("2026-07-15T13:00:00Z");
  });

  test("map pin popup shows the resolved timezone and abbreviation, not raw UTC", async ({
    page,
  }) => {
    await mockApis(
      page,
      [{ latitude: 40.4168, longitude: -3.7038, recorded_at: "2026-07-15T13:00:00Z" }],
      "Europe/Madrid",
    );
    const myVehicles = new MyVehiclesPage(page);
    await myVehicles.goto();
    await myVehicles.openHistoryModal("My Toyota");

    await myVehicles.historyModal.locator(".leaflet-marker-icon").first().click();
    const popup = page.locator(".leaflet-popup");
    await expect(popup).toContainText("15:00");
    await expect(popup).toContainText("CEST");
  });

  test("the same Europe/Madrid preference shows CET for a January entry and CEST for a July entry", async ({
    page,
  }) => {
    await mockApis(
      page,
      [
        { latitude: 40.4168, longitude: -3.7038, recorded_at: "2026-07-15T13:00:00Z" },
        { latitude: 40.4168, longitude: -3.7038, recorded_at: "2026-01-15T13:00:00Z" },
      ],
      "Europe/Madrid",
    );
    const myVehicles = new MyVehiclesPage(page);
    await myVehicles.goto();
    await myVehicles.openHistoryModal("My Toyota");

    await expect(myVehicles.historyModal).toContainText("CEST");
    await expect(myVehicles.historyModal).toContainText("CET");
  });

  test("falls back to the browser-detected timezone when no preference is saved", async ({
    page,
  }) => {
    await page.emulateMedia({});
    await mockApis(
      page,
      [{ latitude: 40.4168, longitude: -3.7038, recorded_at: "2026-07-15T13:00:00Z" }],
      null, // no saved preference
    );
    const myVehicles = new MyVehiclesPage(page);
    await myVehicles.goto();
    await myVehicles.openHistoryModal("My Toyota");

    // Never renders the raw ISO string regardless of which zone the
    // browser resolves to.
    await expect(myVehicles.historyModal).not.toContainText("2026-07-15T13:00:00Z");
  });
});
