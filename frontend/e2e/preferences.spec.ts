import { expect, type Page } from "@playwright/test";
import { test as base } from "./fixtures/coverage";
import { test } from "./fixtures/auth";
import { PreferencesPage } from "./pages/PreferencesPage";

// ---------------------------------------------------------------------------
// Mock data
// ---------------------------------------------------------------------------

const DEFAULT_PREFERENCES = {
  default_ticket_duration_minutes: 60,
  auto_create_ticket: false,
  preferred_notification_channel: null as string | null,
  notification_language: null as string | null,
  timezone: null as string | null,
};

type NotificationConfigFieldSchema = { type: string; min?: number };
type NotificationType = {
  key: string;
  label: string;
  config_schema: Record<string, NotificationConfigFieldSchema>;
};
type NotificationPreference = {
  type_key: string;
  enabled: boolean;
  config: Record<string, number>;
};

// Two catalog types, both declaring a `threshold_m` config field — mirrors
// the seeded `notification_types` rows from the backend migration.
const DEFAULT_NOTIFICATION_TYPES: NotificationType[] = [
  {
    key: "location_moved",
    label: "Vehicle moved",
    config_schema: { threshold_m: { type: "integer", min: 1 } },
  },
  {
    key: "ser_zone_ticket_required",
    label: "SER ticket required",
    config_schema: { threshold_m: { type: "integer", min: 1 } },
  },
];

// Both types enabled by default so the page genuinely renders their toggles
// and inline config controls rather than falling into the error branch.
function defaultNotificationPreferences(): NotificationPreference[] {
  return [
    { type_key: "location_moved", enabled: true, config: { threshold_m: 50 } },
    { type_key: "ser_zone_ticket_required", enabled: true, config: { threshold_m: 50 } },
  ];
}

// ---------------------------------------------------------------------------
// Route mock helper
// ---------------------------------------------------------------------------

/**
 * Wires up GET/PUT /api/preferences route handlers for a given test page,
 * plus GET /api/notifications/channels (PreferencesPage's preferred-channel
 * select is populated from the user's connected channels), GET
 * /api/notifications/languages (populates the notification-language select),
 * GET /api/notifications/types, and GET/PUT /api/notifications/preferences
 * (PreferencesPage's `load()` calls all five of these via `Promise.all`, so
 * all five must be mocked or the page falls into its generic error branch).
 * `preferences` and `notificationPreferences` are mutated in-place by their
 * respective PUT handlers so a subsequent GET (if any) reflects the latest
 * saved values within the same test.
 */
async function mockPreferencesApis(
  page: Page,
  preferences = { ...DEFAULT_PREFERENCES },
  connectedChannels: string[] = [],
  notificationTypes: NotificationType[] = DEFAULT_NOTIFICATION_TYPES,
  notificationPreferences: NotificationPreference[] = defaultNotificationPreferences(),
) {
  await page.route("**/api/notifications/channels", async (route, request) => {
    if (request.method() === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ channels: connectedChannels }),
      });
    }
  });

  await page.route("**/api/notifications/languages", async (route, request) => {
    if (request.method() === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ languages: ["en", "es"] }),
      });
    }
  });

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
        preferred_notification_channel: string | null;
        notification_language: string | null;
        timezone: string | null;
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
      preferences.preferred_notification_channel =
        body.preferred_notification_channel;
      preferences.notification_language = body.notification_language;
      preferences.timezone = body.timezone;
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(preferences),
      });
    }
  });

  await page.route("**/api/notifications/types", async (route, request) => {
    if (request.method() === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(notificationTypes),
      });
    }
  });

  await page.route("**/api/notifications/preferences", async (route, request) => {
    if (request.method() === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(notificationPreferences),
      });
    }
  });

  await page.route("**/api/notifications/preferences/*", async (route, request) => {
    if (request.method() !== "PUT") return;
    const typeKey = new URL(request.url()).pathname.split("/").pop() ?? "";
    const body = (await request.postDataJSON()) as {
      enabled: boolean;
      config: Record<string, number>;
    };
    const updated: NotificationPreference = {
      type_key: typeKey,
      enabled: body.enabled,
      config: body.config,
    };
    const existing = notificationPreferences.find((p) => p.type_key === typeKey);
    if (existing) {
      existing.enabled = updated.enabled;
      existing.config = updated.config;
    } else {
      notificationPreferences.push(updated);
    }
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(updated),
    });
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

  test("user with no connected channels sees no selectable preferred-channel options", async ({
    page,
  }) => {
    await mockPreferencesApis(page, { ...DEFAULT_PREFERENCES }, []);
    const preferences = new PreferencesPage(page);
    await preferences.goto();

    await expect(preferences.heading).toBeVisible();
    await expect(preferences.noChannelsConnectedMessage).toBeVisible();
    await expect(preferences.preferredChannelSelect).toHaveCount(0);
  });

  test("picking a connected channel as preferred sends it in PUT and reflects on save", async ({
    page,
  }) => {
    await mockPreferencesApis(page, { ...DEFAULT_PREFERENCES }, ["telegram"]);
    const preferences = new PreferencesPage(page);
    await preferences.goto();

    await preferences.setPreferredChannel("Telegram");

    const [putRequest] = await Promise.all([
      page.waitForRequest(
        (req) =>
          req.url().includes("/api/preferences") && req.method() === "PUT",
      ),
      preferences.save(),
    ]);

    const body = putRequest.postDataJSON() as {
      preferred_notification_channel: string | null;
    };
    expect(body.preferred_notification_channel).toBe("telegram");
    await expect(preferences.savedMessage).toBeVisible();
  });

  test("picking a notification language sends it in PUT and reflects on save", async ({
    page,
  }) => {
    await mockPreferencesApis(page);
    const preferences = new PreferencesPage(page);
    await preferences.goto();

    await preferences.setNotificationLanguage("Spanish");

    const [putRequest] = await Promise.all([
      page.waitForRequest(
        (req) =>
          req.url().includes("/api/preferences") && req.method() === "PUT",
      ),
      preferences.save(),
    ]);

    const body = putRequest.postDataJSON() as {
      notification_language: string | null;
    };
    expect(body.notification_language).toBe("es");
    await expect(preferences.savedMessage).toBeVisible();
  });

  test("toggling a notification type off and saving sends PUT with enabled: false", async ({
    page,
  }) => {
    await mockPreferencesApis(page);
    const preferences = new PreferencesPage(page);
    await preferences.goto();

    await expect(preferences.notificationToggle("ser_zone_ticket_required")).toBeChecked();

    await preferences.setNotificationEnabled("ser_zone_ticket_required", false);

    const [putRequest] = await Promise.all([
      page.waitForRequest(
        (req) =>
          req.url().includes("/api/notifications/preferences/ser_zone_ticket_required") &&
          req.method() === "PUT",
      ),
      preferences.save(),
    ]);

    const body = putRequest.postDataJSON() as { enabled: boolean; config: Record<string, number> };
    expect(body.enabled).toBe(false);
    await expect(preferences.savedMessage).toBeVisible();
  });

  test("editing a type's threshold and saving sends PUT with the new config", async ({
    page,
  }) => {
    await mockPreferencesApis(page);
    const preferences = new PreferencesPage(page);
    await preferences.goto();

    await expect(preferences.notificationThresholdInput("location_moved")).toHaveValue("50");

    await preferences.setNotificationThreshold("location_moved", 75);

    const [putRequest] = await Promise.all([
      page.waitForRequest(
        (req) =>
          req.url().includes("/api/notifications/preferences/location_moved") &&
          req.method() === "PUT",
      ),
      preferences.save(),
    ]);

    const body = putRequest.postDataJSON() as { enabled: boolean; config: Record<string, number> };
    expect(body.config).toEqual({ threshold_m: 75 });
    await expect(preferences.savedMessage).toBeVisible();
  });

  test("disabling a notification type hides its inline config control", async ({ page }) => {
    await mockPreferencesApis(page);
    const preferences = new PreferencesPage(page);
    await preferences.goto();

    await expect(preferences.notificationThresholdInput("location_moved")).toBeVisible();

    await preferences.setNotificationEnabled("location_moved", false);

    await expect(preferences.notificationThresholdInput("location_moved")).toHaveCount(0);
  });

  test("searching for a timezone, selecting it, and saving sends it in PUT and reflects on reload", async ({
    page,
  }) => {
    const preferencesState = { ...DEFAULT_PREFERENCES };
    await mockPreferencesApis(page, preferencesState);
    const preferences = new PreferencesPage(page);
    await preferences.goto();

    await preferences.searchTimezone("Madrid");
    await preferences.setTimezone("Europe/Madrid");

    const [putRequest] = await Promise.all([
      page.waitForRequest(
        (req) =>
          req.url().includes("/api/preferences") && req.method() === "PUT",
      ),
      preferences.save(),
    ]);

    const body = putRequest.postDataJSON() as { timezone: string | null };
    expect(body.timezone).toBe("Europe/Madrid");
    await expect(preferences.savedMessage).toBeVisible();

    // Reload the page — the mocked GET now reflects the previously-saved
    // PUT body, so the combobox input should come back pre-populated with
    // the selected option's full label (zone id + abbreviation).
    await preferences.goto();
    await expect(preferences.timezoneSearchInput).toHaveValue(/Europe\/Madrid/);
  });

  test("clearing a saved timezone and saving sends null in PUT", async ({ page }) => {
    const preferencesState = { ...DEFAULT_PREFERENCES, timezone: "Europe/Madrid" };
    await mockPreferencesApis(page, preferencesState);
    const preferences = new PreferencesPage(page);
    await preferences.goto();

    await expect(preferences.timezoneSearchInput).toHaveValue(/Europe\/Madrid/);

    await preferences.clearTimezone();

    const [putRequest] = await Promise.all([
      page.waitForRequest(
        (req) =>
          req.url().includes("/api/preferences") && req.method() === "PUT",
      ),
      preferences.save(),
    ]);

    const body = putRequest.postDataJSON() as { timezone: string | null };
    expect(body.timezone).toBeNull();
    await expect(preferences.savedMessage).toBeVisible();
  });

  test("typing in the timezone search shows a live-filtered dropdown and does not submit the form on Enter", async ({
    page,
  }) => {
    const preferencesState = { ...DEFAULT_PREFERENCES };
    await mockPreferencesApis(page, preferencesState);
    const preferences = new PreferencesPage(page);
    await preferences.goto();

    let putRequestFired = false;
    page.on("request", (req) => {
      if (req.url().includes("/api/preferences") && req.method() === "PUT") {
        putRequestFired = true;
      }
    });

    await preferences.searchTimezone("Madrid");

    // The bug: a plain <select> never visibly updates while typing. The fix
    // renders a real listbox below the input that reflects the filter live,
    // without needing to open/click anything else first.
    await expect(page.getByRole("option", { name: /Europe\/Madrid/ })).toBeVisible();

    // Pressing Enter must never trigger the page's native form submit (the
    // original bug). It's allowed to commit the top filtered match instead.
    await preferences.timezoneSearchInput.press("Enter");

    expect(putRequestFired).toBe(false);
    await expect(preferences.savedMessage).not.toBeVisible();
    await expect(preferences.timezoneSearchInput).toHaveValue(/Europe\/Madrid/);
  });
});
