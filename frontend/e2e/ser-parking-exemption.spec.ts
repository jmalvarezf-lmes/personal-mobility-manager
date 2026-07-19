import { expect, type Page } from "@playwright/test";
import { test } from "./fixtures/auth";
import { MyVehiclesPage } from "./pages/MyVehiclesPage";

// ---------------------------------------------------------------------------
// Mock data
// ---------------------------------------------------------------------------

const VEHICLE_ID = "00000000-0000-0000-0000-000000000020";

const MOCK_VEHICLES = [
  {
    vehicle_id: VEHICLE_ID,
    brand: "generic",
    display_name: "Exemption Test Car",
    vin: null,
    location: null,
    ambient_label: null,
  },
];

const MOCK_VEHICLE_DETAIL = {
  vehicle_id: VEHICLE_ID,
  brand: "generic",
  display_name: "Exemption Test Car",
  vin: null,
  config: { location_token: "abc123-token-uuid" },
};

const MOCK_CITIES = [
  { code: "madrid", name: "Madrid" },
  { code: "barcelona", name: "Barcelona" },
];

// Lightweight zone_number/neighbourhood pairs — what the picker's zone
// <select> actually consumes via GET /parking/ser-zone-options. Kept
// separate from the (still-mocked) heavy GET /parking/ser-zones response
// used for map rendering elsewhere in the app.
const MOCK_ZONE_OPTIONS_RESPONSE = {
  city: "madrid",
  options: [
    { zone_number: "163", neighbourhood: "Sol" },
    { zone_number: "200", neighbourhood: "Malasaña" },
  ],
};

const MOCK_ZONES_RESPONSE = {
  city: "madrid",
  zones: [],
  frontiers: [
    { zone_number: "163", neighbourhood: "Sol", geometry: { type: "Polygon", coordinates: [] } },
    { zone_number: "200", neighbourhood: "Malasaña", geometry: { type: "Polygon", coordinates: [] } },
  ],
};

type StoredExemption = { city_code: string | null; zone_number: string | null };

// ---------------------------------------------------------------------------
// Route mock helper
// ---------------------------------------------------------------------------

async function mockApis(page: Page, initialExemption?: StoredExemption) {
  let storedExemption: StoredExemption = initialExemption ?? { city_code: null, zone_number: null };

  await page.route("**/api/config", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ osm_tile_url: null }),
    }),
  );

  await page.route("**/api/parking/ser-zone-options**", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(MOCK_ZONE_OPTIONS_RESPONSE),
    }),
  );

  await page.route("**/api/parking/ser-zones**", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(MOCK_ZONES_RESPONSE),
    }),
  );

  await page.route("**/api/ambient-labels/*/icon", (route) =>
    route.fulfill({
      status: 200,
      contentType: "image/svg+xml",
      body: "<svg xmlns='http://www.w3.org/2000/svg'></svg>",
    }),
  );

  await page.route("**/api/cities", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(MOCK_CITIES),
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

  await page.route("**/api/vehicles/*", async (route, request) => {
    const method = request.method();

    if (method === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(MOCK_VEHICLE_DETAIL),
      });
    } else if (method === "PUT") {
      // Vehicle-fields update — the single "Save" button's primary call,
      // which must succeed before the exemption reconciliation call below
      // is attempted (see EditVehicleModal.handleSubmit).
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(MOCK_VEHICLE_DETAIL),
      });
    } else {
      await route.continue();
    }
  });

  await page.route(`**/api/vehicles/${VEHICLE_ID}/ser-parking-exemptions`, async (route, request) => {
    const method = request.method();
    if (method === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(storedExemption),
      });
    } else if (method === "POST") {
      const body = (await request.postDataJSON()) as { city_code: string; zone_number: string };
      storedExemption = { city_code: body.city_code, zone_number: body.zone_number };
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(storedExemption),
      });
    } else if (method === "DELETE") {
      storedExemption = { city_code: null, zone_number: null };
      await route.fulfill({ status: 204 });
    }
  });
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

test.describe("SER parking exemption picker", () => {
  test("opening the edit modal shows the city selector populated, zone selector empty until a city is chosen", async ({
    page,
  }) => {
    await mockApis(page);
    const myVehicles = new MyVehiclesPage(page);
    await myVehicles.goto();
    await myVehicles.openEditModal("Exemption Test Car");

    await expect(myVehicles.exemptionCitySelect).toBeVisible();
    const cityOptions = await myVehicles.exemptionCitySelect.locator("option").allTextContents();
    expect(cityOptions.join(" ")).toContain("Madrid");
    expect(cityOptions.join(" ")).toContain("Barcelona");

    const zoneOptionsBefore = await myVehicles.exemptionZoneSelect.locator("option").count();
    expect(zoneOptionsBefore).toBe(1); // only the placeholder option
  });

  test("selecting a city loads its SER zones labeled by neighbourhood", async ({ page }) => {
    await mockApis(page);
    const myVehicles = new MyVehiclesPage(page);
    await myVehicles.goto();
    await myVehicles.openEditModal("Exemption Test Car");

    await myVehicles.selectExemptionCity("Madrid");

    await expect(myVehicles.exemptionZoneSelect).toBeEnabled();
    const zoneOptions = await myVehicles.exemptionZoneSelect.locator("option").allTextContents();
    expect(zoneOptions.join(" ")).toContain("Sol");
    expect(zoneOptions.join(" ")).toContain("Malasaña");
  });

  test("selecting a city then a zone and clicking the single Save button persists the exemption", async ({
    page,
  }) => {
    await mockApis(page);
    const myVehicles = new MyVehiclesPage(page);
    await myVehicles.goto();
    await myVehicles.openEditModal("Exemption Test Car");

    await myVehicles.selectExemptionCity("Madrid");
    await myVehicles.selectExemptionZone("Sol");

    const [putRequest, postRequest] = await Promise.all([
      page.waitForRequest(
        (req) => req.url().includes(`/api/vehicles/${VEHICLE_ID}`) && req.method() === "PUT",
      ),
      page.waitForRequest(
        (req) =>
          req.url().includes(`/api/vehicles/${VEHICLE_ID}/ser-parking-exemptions`) &&
          req.method() === "POST",
      ),
      myVehicles.saveExemption(),
    ]);

    // Both the vehicle-fields update and the exemption upsert are triggered
    // by the same single "Save" click — there is no separate exemption save
    // action.
    expect(putRequest.method()).toBe("PUT");
    const body = postRequest.postDataJSON() as { city_code: string; zone_number: string };
    expect(body.city_code).toBe("madrid");
    expect(body.zone_number).toBe("163");
  });

  test("clicking Clear alone does not call any exemption API — it is a local reset only", async ({
    page,
  }) => {
    await mockApis(page);
    const myVehicles = new MyVehiclesPage(page);
    await myVehicles.goto();
    await myVehicles.openEditModal("Exemption Test Car");

    await myVehicles.selectExemptionCity("Madrid");
    await myVehicles.selectExemptionZone("Sol");

    const exemptionRequestMethods: string[] = [];
    page.on("request", (req) => {
      if (req.url().includes(`/api/vehicles/${VEHICLE_ID}/ser-parking-exemptions`)) {
        exemptionRequestMethods.push(req.method());
      }
    });

    await myVehicles.clearExemption();
    // The picker resets locally and immediately — no network round trip is
    // needed to observe that, so a short settle window is enough to prove
    // no (incorrect) immediate call was fired.
    await page.waitForTimeout(200);

    expect(exemptionRequestMethods).toEqual([]);
    await expect(myVehicles.exemptionCitySelect).toHaveValue("");
  });

  test("clearing an existing exemption and saving sends a DELETE request", async ({ page }) => {
    await mockApis(page, { city_code: "madrid", zone_number: "163" });
    const myVehicles = new MyVehiclesPage(page);
    await myVehicles.goto();
    await myVehicles.openEditModal("Exemption Test Car");

    await myVehicles.clearExemption();

    const [deleteRequest] = await Promise.all([
      page.waitForRequest(
        (req) =>
          req.url().includes(`/api/vehicles/${VEHICLE_ID}/ser-parking-exemptions`) &&
          req.method() === "DELETE",
      ),
      myVehicles.saveExemption(),
    ]);

    expect(deleteRequest.method()).toBe("DELETE");
  });

  test("opening the edit modal for a vehicle with an existing exemption pre-selects its zone", async ({
    page,
  }) => {
    await mockApis(page, { city_code: "madrid", zone_number: "163" });
    const myVehicles = new MyVehiclesPage(page);
    await myVehicles.goto();
    await myVehicles.openEditModal("Exemption Test Car");

    // Uses the lightweight GET /parking/ser-zone-options fetch, not the
    // heavy GET /parking/ser-zones map-rendering endpoint — so the correct
    // option is selected as soon as it resolves, without waiting on
    // geometry the picker never uses.
    await expect(myVehicles.exemptionCitySelect).toHaveValue("madrid");
    await expect(myVehicles.exemptionZoneSelect).toHaveValue("163");
  });
});
