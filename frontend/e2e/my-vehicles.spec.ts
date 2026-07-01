import { expect, test as base, type Page } from "@playwright/test";
import { test } from "./fixtures/auth";
import { MyVehiclesPage } from "./pages/MyVehiclesPage";

// ---------------------------------------------------------------------------
// Mock data
// ---------------------------------------------------------------------------

const TOYOTA_ID = "00000000-0000-0000-0000-000000000010";
const GENERIC_ID = "00000000-0000-0000-0000-000000000011";

const MOCK_VEHICLES = [
  {
    vehicle_id: TOYOTA_ID,
    brand: "toyota",
    display_name: "My Toyota",
    vin: "JTDBF3EJ8A3045678",
    location: {
      latitude: 40.4168,
      longitude: -3.7038,
      recorded_at: "2026-07-01T10:00:00Z",
    },
  },
  {
    vehicle_id: GENERIC_ID,
    brand: "generic",
    display_name: "My Scooter",
    vin: null,
    location: null,
  },
];

const MOCK_TOYOTA_DETAIL = {
  vehicle_id: TOYOTA_ID,
  brand: "toyota",
  display_name: "My Toyota",
  vin: "JTDBF3EJ8A3045678",
  config: { username: "driver@example.com", locale: "en", password: "●●●●●●●●" },
};

const MOCK_GENERIC_DETAIL = {
  vehicle_id: GENERIC_ID,
  brand: "generic",
  display_name: "My Scooter",
  vin: null,
  config: { location_token: "abc123-token-uuid" },
};

// ---------------------------------------------------------------------------
// Route mock helper
// ---------------------------------------------------------------------------

/**
 * Wires up all /api/vehicles route handlers for a given test page.
 * `vehicles` is mutated in-place by POST/DELETE so GET always reflects
 * the current list within the same test without re-routing.
 */
async function mockVehicleApis(
  page: Page,
  vehicles = [...MOCK_VEHICLES] as typeof MOCK_VEHICLES,
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

  // GET /api/vehicles — list  |  POST /api/vehicles — create
  await page.route("**/api/vehicles", async (route, request) => {
    if (request.method() === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(vehicles),
      });
    } else if (request.method() === "POST") {
      const body = (await request.postDataJSON()) as {
        brand: string;
        display_name: string;
      };
      const newVehicle = {
        vehicle_id: "00000000-0000-0000-0000-000000000099",
        brand: body.brand,
        display_name: body.display_name,
        vin: null,
        location: null,
        ...(body.brand === "generic" ? { location_token: "new-token-uuid" } : {}),
      };
      vehicles.push(newVehicle as (typeof MOCK_VEHICLES)[number]);
      await route.fulfill({
        status: 201,
        contentType: "application/json",
        body: JSON.stringify(newVehicle),
      });
    }
  });

  // GET /api/vehicles/:id — detail  |  PUT — update  |  DELETE — delete
  await page.route("**/api/vehicles/*", async (route, request) => {
    const id = request.url().split("/").pop()!;
    const method = request.method();

    if (method === "GET") {
      const detail =
        id === TOYOTA_ID ? MOCK_TOYOTA_DETAIL : MOCK_GENERIC_DETAIL;
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(detail),
      });
    } else if (method === "PUT") {
      const body = (await request.postDataJSON()) as { display_name: string };
      const baseDetail =
        id === TOYOTA_ID ? MOCK_TOYOTA_DETAIL : MOCK_GENERIC_DETAIL;
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ ...baseDetail, display_name: body.display_name }),
      });
    } else if (method === "DELETE") {
      const idx = vehicles.findIndex((v) => v.vehicle_id === id);
      if (idx !== -1) vehicles.splice(idx, 1);
      await route.fulfill({ status: 204 });
    }
  });
}

// ---------------------------------------------------------------------------
// Auth guard — unauthenticated scenarios use the base test (no auth mock)
// ---------------------------------------------------------------------------

base.describe("Auth guard", () => {
  base("unauthenticated user is redirected from /my-vehicles to /", async ({ page }) => {
    await page.route("**/api/auth/me", (route) =>
      route.fulfill({ status: 401 }),
    );
    await page.goto("/my-vehicles");
    await expect(page).toHaveURL("/");
  });
});

// ---------------------------------------------------------------------------
// Navigation
// ---------------------------------------------------------------------------

test.describe("Navigation", () => {
  test("shows My Vehicles link in nav when logged in", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByRole("link", { name: "My Vehicles" })).toBeVisible();
  });

  base("does not show My Vehicles link when logged out", async ({ page }) => {
    await page.route("**/api/auth/me", (route) =>
      route.fulfill({ status: 401 }),
    );
    await page.goto("/");
    await expect(
      page.getByRole("link", { name: "My Vehicles" }),
    ).not.toBeVisible();
  });
});

// ---------------------------------------------------------------------------
// My Vehicles page — authenticated tests
// ---------------------------------------------------------------------------

test.describe("My Vehicles page", () => {
  test("shows page heading and Add Vehicle button", async ({ page }) => {
    await mockVehicleApis(page, []);
    const myVehicles = new MyVehiclesPage(page);
    await myVehicles.goto();
    await expect(myVehicles.heading).toBeVisible();
    await expect(myVehicles.addVehicleButton).toBeVisible();
  });

  test("shows empty state when user has no vehicles", async ({ page }) => {
    await mockVehicleApis(page, []);
    const myVehicles = new MyVehiclesPage(page);
    await myVehicles.goto();
    await expect(myVehicles.vehicleCards).toHaveCount(0);
    await expect(page.getByText(/no vehicles|add your first/i)).toBeVisible();
  });

  test("renders one card per vehicle", async ({ page }) => {
    await mockVehicleApis(page);
    const myVehicles = new MyVehiclesPage(page);
    await myVehicles.goto();
    await expect(myVehicles.vehicleCards).toHaveCount(2);
  });
});

// ---------------------------------------------------------------------------
// Vehicle card content
// ---------------------------------------------------------------------------

test.describe("Vehicle card content", () => {
  test.beforeEach(async ({ page }) => {
    await mockVehicleApis(page);
  });

  test("Toyota card shows username, locale, vin, and masked password", async ({
    page,
  }) => {
    const myVehicles = new MyVehiclesPage(page);
    await myVehicles.goto();
    const card = myVehicles.vehicleCard("My Toyota");
    await expect(card).toContainText("driver@example.com");
    await expect(card).toContainText("en");
    await expect(card).toContainText("JTDBF3EJ8A3045678");
    await expect(card).toContainText("●●●●●●●●");
  });

  test("Generic card shows the constructed push URL", async ({ page }) => {
    const myVehicles = new MyVehiclesPage(page);
    await myVehicles.goto();
    const card = myVehicles.vehicleCard("My Scooter");
    await expect(card).toContainText("abc123-token-uuid");
    await expect(card).toContainText("/api/vehicles/");
    await expect(card).toContainText("/location");
  });

  test("card with location shows coordinates", async ({ page }) => {
    const myVehicles = new MyVehiclesPage(page);
    await myVehicles.goto();
    const card = myVehicles.vehicleCard("My Toyota");
    await expect(card).toContainText("40.4168");
    await expect(card).toContainText("-3.7038");
  });

  test("card without location shows placeholder text", async ({ page }) => {
    const myVehicles = new MyVehiclesPage(page);
    await myVehicles.goto();
    const card = myVehicles.vehicleCard("My Scooter");
    await expect(card).toContainText(/no location/i);
  });
});

// ---------------------------------------------------------------------------
// Map
// ---------------------------------------------------------------------------

test.describe("Vehicle map", () => {
  test("shared map is visible on page load", async ({ page }) => {
    await mockVehicleApis(page);
    const myVehicles = new MyVehiclesPage(page);
    await myVehicles.goto();
    await expect(myVehicles.map).toBeVisible();
  });

  test("car marker appears for each vehicle with a known location", async ({
    page,
  }) => {
    await mockVehicleApis(page);
    const myVehicles = new MyVehiclesPage(page);
    await myVehicles.goto();
    // Only the Toyota vehicle has a location — one DivIcon marker expected
    await expect(myVehicles.carMarkers).toHaveCount(1);
  });

  test("no car markers when no vehicle has a location", async ({ page }) => {
    const vehiclesWithoutLocation = [
      { ...MOCK_VEHICLES[0]!, location: null },
      { ...MOCK_VEHICLES[1]! },
    ] as typeof MOCK_VEHICLES;
    await mockVehicleApis(page, vehiclesWithoutLocation);
    const myVehicles = new MyVehiclesPage(page);
    await myVehicles.goto();
    await expect(myVehicles.carMarkers).toHaveCount(0);
  });

  test("clicking a car marker shows a popup with the vehicle name", async ({
    page,
  }) => {
    await mockVehicleApis(page);
    const myVehicles = new MyVehiclesPage(page);
    await myVehicles.goto();
    await myVehicles.carMarkers.first().click();
    await expect(page.locator(".leaflet-popup")).toContainText("My Toyota");
  });
});

// ---------------------------------------------------------------------------
// Add Vehicle
// ---------------------------------------------------------------------------

test.describe("Add Vehicle", () => {
  test("Add Vehicle button opens the modal", async ({ page }) => {
    await mockVehicleApis(page, []);
    const myVehicles = new MyVehiclesPage(page);
    await myVehicles.goto();
    await myVehicles.openAddModal();
    await expect(myVehicles.modal).toBeVisible();
  });

  test("creating a Generic vehicle sends correct POST and shows new card", async ({
    page,
  }) => {
    await mockVehicleApis(page, []);
    const myVehicles = new MyVehiclesPage(page);
    await myVehicles.goto();
    await myVehicles.openAddModal();
    await myVehicles.selectBrand("generic");
    await myVehicles.fillGenericFields({ displayName: "New Van" });

    const [postRequest] = await Promise.all([
      page.waitForRequest(
        (req) =>
          req.url().includes("/api/vehicles") && req.method() === "POST",
      ),
      myVehicles.submitModal(),
    ]);

    const body = postRequest.postDataJSON() as { brand: string; display_name: string };
    expect(body.brand).toBe("generic");
    expect(body.display_name).toBe("New Van");

    await expect(myVehicles.modal).not.toBeVisible();
    await expect(myVehicles.vehicleCard("New Van")).toBeVisible();
  });

  test("creating a Toyota vehicle sends correct POST payload", async ({
    page,
  }) => {
    await mockVehicleApis(page, []);
    const myVehicles = new MyVehiclesPage(page);
    await myVehicles.goto();
    await myVehicles.openAddModal();
    await myVehicles.selectBrand("toyota");
    await myVehicles.fillToyotaFields({
      displayName: "New Toyota",
      vin: "VIN123",
      username: "u@mail.com",
      password: "secret",
      locale: "es",
    });

    const [postRequest] = await Promise.all([
      page.waitForRequest(
        (req) =>
          req.url().includes("/api/vehicles") && req.method() === "POST",
      ),
      myVehicles.submitModal(),
    ]);

    const body = postRequest.postDataJSON() as Record<string, string>;
    expect(body.brand).toBe("toyota");
    expect(body.display_name).toBe("New Toyota");
    expect(body.username).toBe("u@mail.com");
    expect(body.locale).toBe("es");
  });

  test("API error on create shows inline error message", async ({ page }) => {
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
    await page.route("**/api/vehicles", async (route, request) => {
      if (request.method() === "GET") {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify([]),
        });
      } else if (request.method() === "POST") {
        await route.fulfill({
          status: 422,
          contentType: "application/json",
          body: JSON.stringify({ detail: "Brand not enabled" }),
        });
      }
    });

    const myVehicles = new MyVehiclesPage(page);
    await myVehicles.goto();
    await myVehicles.openAddModal();
    await myVehicles.selectBrand("generic");
    await myVehicles.fillGenericFields({ displayName: "Bad Vehicle" });
    await myVehicles.submitModal();

    await expect(myVehicles.modal).toBeVisible();
    await expect(
      myVehicles.modal.getByRole("alert").or(
        myVehicles.modal.locator("[data-testid='error']"),
      ),
    ).toBeVisible();
  });
});

// ---------------------------------------------------------------------------
// Edit Vehicle
// ---------------------------------------------------------------------------

test.describe("Edit Vehicle", () => {
  test.beforeEach(async ({ page }) => {
    await mockVehicleApis(page);
  });

  test("Edit opens modal pre-filled with vehicle display_name", async ({
    page,
  }) => {
    const myVehicles = new MyVehiclesPage(page);
    await myVehicles.goto();
    await myVehicles.openEditModal("My Toyota");
    await expect(myVehicles.modalDisplayNameInput).toHaveValue("My Toyota");
  });

  test("updating display_name only sends PUT without password", async ({
    page,
  }) => {
    const myVehicles = new MyVehiclesPage(page);
    await myVehicles.goto();
    await myVehicles.openEditModal("My Toyota");
    await myVehicles.modalDisplayNameInput.fill("Toyota Updated");
    // Password field intentionally left empty

    const [putRequest] = await Promise.all([
      page.waitForRequest(
        (req) =>
          req.url().includes(`/api/vehicles/${TOYOTA_ID}`) &&
          req.method() === "PUT",
      ),
      myVehicles.submitModal(),
    ]);

    const body = putRequest.postDataJSON() as Record<string, string | null | undefined>;
    expect(body.display_name).toBe("Toyota Updated");
    expect(body.password == null || body.password === "").toBe(true);
    await expect(myVehicles.modal).not.toBeVisible();
  });

  test("updating credentials sends PUT with new password", async ({ page }) => {
    const myVehicles = new MyVehiclesPage(page);
    await myVehicles.goto();
    await myVehicles.openEditModal("My Toyota");
    await myVehicles.modalPasswordInput.fill("new-secret");

    const [putRequest] = await Promise.all([
      page.waitForRequest(
        (req) =>
          req.url().includes(`/api/vehicles/${TOYOTA_ID}`) &&
          req.method() === "PUT",
      ),
      myVehicles.submitModal(),
    ]);

    const body = putRequest.postDataJSON() as Record<string, string>;
    expect(body.password).toBe("new-secret");
  });

  test("Generic edit modal shows only display_name field", async ({ page }) => {
    const myVehicles = new MyVehiclesPage(page);
    await myVehicles.goto();
    await myVehicles.openEditModal("My Scooter");
    await expect(myVehicles.modalDisplayNameInput).toBeVisible();
    await expect(myVehicles.modalPasswordInput).not.toBeVisible();
  });

  test("cancelling edit does not send a PUT request", async ({ page }) => {
    let putCalled = false;
    page.on("request", (req) => {
      if (req.method() === "PUT") putCalled = true;
    });

    const myVehicles = new MyVehiclesPage(page);
    await myVehicles.goto();
    await myVehicles.openEditModal("My Toyota");
    await myVehicles.cancelModal();

    await expect(myVehicles.modal).not.toBeVisible();
    expect(putCalled).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// Delete Vehicle
// ---------------------------------------------------------------------------

test.describe("Delete Vehicle", () => {
  test("confirming delete sends DELETE and removes the card", async ({
    page,
  }) => {
    await mockVehicleApis(page);
    const myVehicles = new MyVehiclesPage(page);
    await myVehicles.goto();
    await expect(myVehicles.vehicleCard("My Toyota")).toBeVisible();

    page.on("dialog", (dialog) => void dialog.accept());

    const [deleteRequest] = await Promise.all([
      page.waitForRequest(
        (req) =>
          req.url().includes(`/api/vehicles/${TOYOTA_ID}`) &&
          req.method() === "DELETE",
      ),
      myVehicles.deleteButton("My Toyota").click(),
    ]);

    expect(deleteRequest.method()).toBe("DELETE");
    await expect(myVehicles.vehicleCard("My Toyota")).not.toBeVisible();
  });

  test("cancelling delete leaves the card intact", async ({ page }) => {
    await mockVehicleApis(page);
    let deleteCalled = false;
    page.on("request", (req) => {
      if (req.method() === "DELETE") deleteCalled = true;
    });
    page.on("dialog", (dialog) => void dialog.dismiss());

    const myVehicles = new MyVehiclesPage(page);
    await myVehicles.goto();
    await myVehicles.deleteButton("My Toyota").click();

    await expect(myVehicles.vehicleCard("My Toyota")).toBeVisible();
    expect(deleteCalled).toBe(false);
  });

  test("DELETE API error shows feedback and keeps the card visible", async ({
    page,
  }) => {
    await mockVehicleApis(page);
    // Override only the Toyota DELETE to fail
    await page.route(`**/api/vehicles/${TOYOTA_ID}`, async (route, request) => {
      if (request.method() === "DELETE") {
        await route.fulfill({
          status: 500,
          contentType: "application/json",
          body: JSON.stringify({ detail: "Internal error" }),
        });
      } else {
        await route.continue();
      }
    });

    page.on("dialog", (dialog) => void dialog.accept());

    const myVehicles = new MyVehiclesPage(page);
    await myVehicles.goto();
    await myVehicles.deleteButton("My Toyota").click();

    // Give the UI time to process the error
    await page.waitForTimeout(500);

    await expect(myVehicles.vehicleCard("My Toyota")).toBeVisible();
    await expect(
      page.getByRole("alert").or(page.locator("[data-testid='error']")),
    ).toBeVisible();
  });
});
