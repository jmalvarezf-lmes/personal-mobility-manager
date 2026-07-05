import { expect, test as base, type Page } from "@playwright/test";
import { test } from "./fixtures/auth";
import { PreferencesPage } from "./pages/PreferencesPage";

// ---------------------------------------------------------------------------
// Mock data
// ---------------------------------------------------------------------------

const DEFAULT_PREFERENCES = {
  default_ticket_duration_minutes: 60,
  auto_create_ticket: false,
};

// ---------------------------------------------------------------------------
// Route mock helper
// ---------------------------------------------------------------------------

/**
 * Wires up GET/PUT /api/preferences route handlers for a given test page.
 * `preferences` is mutated in-place by PUT so a subsequent GET (if any)
 * reflects the latest saved values within the same test.
 */
async function mockPreferencesApis(
  page: Page,
  preferences = { ...DEFAULT_PREFERENCES },
) {
  await page.route("**/api/preferences", async (route, request) => {
    const method = request.method();
    if (method === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(preferences),
      });
    } else if (method === "PUT") {
      const body = (await request.postDataJSON()) as {
        default_ticket_duration_minutes: number;
        auto_create_ticket: boolean;
      };
      if (body.default_ticket_duration_minutes <= 0) {
        await route.fulfill({
          status: 422,
          contentType: "application/json",
          body: JSON.stringify({ detail: "Invalid duration" }),
        });
        return;
      }
      preferences.default_ticket_duration_minutes =
        body.default_ticket_duration_minutes;
      preferences.auto_create_ticket = body.auto_create_ticket;
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(preferences),
      });
    }
  });
}

// ---------------------------------------------------------------------------
// Auth guard — unauthenticated scenarios use the base test (no auth mock)
// ---------------------------------------------------------------------------

base.describe("Auth guard", () => {
  base("unauthenticated user is redirected from /preferences to /", async ({ page }) => {
    await page.route("**/api/auth/me", (route) =>
      route.fulfill({ status: 401 }),
    );
    await page.goto("/preferences");
    await expect(page).toHaveURL("/");
  });
});

// ---------------------------------------------------------------------------
// Preferences page — authenticated tests
// ---------------------------------------------------------------------------

test.describe("Preferences page", () => {
  test("shows current values on load", async ({ page }) => {
    await mockPreferencesApis(page);
    const preferences = new PreferencesPage(page);
    await preferences.goto();

    await expect(preferences.heading).toBeVisible();
    await expect(preferences.durationInput).toHaveValue("60");
    await expect(preferences.autoCreateCheckbox).not.toBeChecked();
  });

  test("editing and saving sends PUT and reflects the updated values", async ({
    page,
  }) => {
    await mockPreferencesApis(page);
    const preferences = new PreferencesPage(page);
    await preferences.goto();

    await preferences.setDuration(90);
    await preferences.setAutoCreate(true);

    const [putRequest] = await Promise.all([
      page.waitForRequest(
        (req) =>
          req.url().includes("/api/preferences") && req.method() === "PUT",
      ),
      preferences.save(),
    ]);

    const body = putRequest.postDataJSON() as {
      default_ticket_duration_minutes: number;
      auto_create_ticket: boolean;
    };
    expect(body.default_ticket_duration_minutes).toBe(90);
    expect(body.auto_create_ticket).toBe(true);

    await expect(preferences.durationInput).toHaveValue("90");
    await expect(preferences.autoCreateCheckbox).toBeChecked();
    await expect(preferences.savedMessage).toBeVisible();
  });

  test("invalid duration shows a validation error without losing entered values", async ({
    page,
  }) => {
    await mockPreferencesApis(page);
    const preferences = new PreferencesPage(page);
    await preferences.goto();

    let putCalled = false;
    page.on("request", (req) => {
      if (req.method() === "PUT" && req.url().includes("/api/preferences")) {
        putCalled = true;
      }
    });

    await preferences.setDuration(0);
    await preferences.save();

    await expect(preferences.errorMessage).toBeVisible();
    await expect(preferences.durationInput).toHaveValue("0");
    expect(putCalled).toBe(false);
  });
});
