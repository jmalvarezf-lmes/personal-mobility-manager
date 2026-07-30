import { expect, type Page } from "@playwright/test";
import { test as base } from "./fixtures/coverage";
import { test } from "./fixtures/auth";
import { NotificationChannelsPage } from "./pages/NotificationChannelsPage";
import { PreferencesPage } from "./pages/PreferencesPage";

// ---------------------------------------------------------------------------
// Mock data
// ---------------------------------------------------------------------------

const AVAILABLE_CHANNELS = ["telegram"];
const DEEP_LINK = "https://t.me/testbot?start=abc123token";

interface MockPreferences {
  default_ticket_duration_minutes: number;
  auto_create_ticket: boolean;
  preferred_notification_channel: string | null;
}

// ---------------------------------------------------------------------------
// Route mock helper
// ---------------------------------------------------------------------------

/**
 * Wires up all notification-channel-related routes plus /api/preferences for
 * a given test page:
 *  - GET /api/notifications/available-channels -> fixed catalog
 *  - GET /api/notifications/languages -> fixed ["en", "es"] catalog;
 *    PreferencesPage's `load()` calls this via `Promise.all` alongside the
 *    other routes below, so it must be mocked too or the page falls into
 *    its generic error branch
 *  - GET /api/notifications/channels -> `connectedChannels`, mutated in
 *    place; simulates the Telegram webhook completing linking after
 *    `autoConnectAfterPolls` polls of this endpoint (there is no real
 *    Telegram webhook to exercise in e2e, so this stands in for it, per the
 *    design's bounded-polling contract)
 *  - DELETE /api/notifications/channels/{channel} -> removes from
 *    `connectedChannels`; also clears `preferences.preferred_notification_channel`
 *    when the disconnected channel was the preferred one, mirroring the
 *    backend's RemoveNotificationChannel side effect
 *  - POST /api/notifications/telegram/link-code -> fixed deep link
 *  - GET/PUT /api/preferences -> `preferences`, mutated in place by PUT
 *  - GET /api/notifications/types and GET /api/notifications/preferences ->
 *    fixed catalog/preferences fixtures. PreferencesPage's `load()` calls
 *    these via `Promise.all` alongside the routes above, so they must be
 *    mocked too or the page falls into its generic error branch (see
 *    preferences.spec.ts's `mockPreferencesApis` for the fuller version of
 *    this fixture used by tests that actually exercise the Notifications
 *    section; this file only needs GETs since no test here toggles them).
 */
async function mockApis(
  page: Page,
  options: {
    connectedChannels?: string[];
    preferences?: MockPreferences;
    /**
     * Milliseconds after the Telegram link-code is issued before
     * "telegram" appears in GET /notifications/channels — stands in for
     * the real Telegram webhook completing linking, which can't be
     * exercised in e2e. Left undefined disables auto-connect entirely.
     */
    autoConnectDelayMs?: number;
  } = {},
) {
  const connectedChannels = options.connectedChannels ?? [];
  const preferences: MockPreferences = options.preferences ?? {
    default_ticket_duration_minutes: 60,
    auto_create_ticket: false,
    preferred_notification_channel: null,
  };

  await page.route("**/api/notifications/available-channels", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ channels: AVAILABLE_CHANNELS }),
    });
  });

  await page.route("**/api/notifications/languages", async (route, request) => {
    if (request.method() !== "GET") {
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ languages: ["en", "es"] }),
    });
  });

  await page.route("**/api/notifications/channels", async (route, request) => {
    if (request.method() !== "GET") {
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ channels: connectedChannels }),
    });
  });

  await page.route("**/api/notifications/channels/*", async (route, request) => {
    if (request.method() !== "DELETE") {
      return;
    }
    const channel = request.url().split("/").pop()!;
    const idx = connectedChannels.indexOf(channel);
    if (idx !== -1) {
      connectedChannels.splice(idx, 1);
    }
    if (preferences.preferred_notification_channel === channel) {
      preferences.preferred_notification_channel = null;
    }
    await route.fulfill({ status: 204 });
  });

  await page.route("**/api/notifications/telegram/link-code", async (route, request) => {
    if (request.method() !== "POST") {
      return;
    }
    if (options.autoConnectDelayMs !== undefined) {
      setTimeout(() => {
        if (!connectedChannels.includes("telegram")) {
          connectedChannels.push("telegram");
        }
      }, options.autoConnectDelayMs);
    }
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ deep_link: DEEP_LINK }),
    });
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
      const body = (await request.postDataJSON()) as MockPreferences;
      preferences.default_ticket_duration_minutes = body.default_ticket_duration_minutes;
      preferences.auto_create_ticket = body.auto_create_ticket;
      preferences.preferred_notification_channel = body.preferred_notification_channel;
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(preferences),
      });
    }
  });

  await page.route("**/api/notifications/types", async (route, request) => {
    if (request.method() !== "GET") {
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([
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
      ]),
    });
  });

  await page.route("**/api/notifications/preferences", async (route, request) => {
    if (request.method() !== "GET") {
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([
        { type_key: "location_moved", enabled: true, config: { threshold_m: 50 } },
        { type_key: "ser_zone_ticket_required", enabled: true, config: { threshold_m: 50 } },
      ]),
    });
  });

  return { connectedChannels, preferences };
}

// ---------------------------------------------------------------------------
// Auth guard — unauthenticated scenarios use the base test (no auth mock)
// ---------------------------------------------------------------------------

base.describe("Auth guard", () => {
  base(
    "unauthenticated user is redirected from /notification-channels to /",
    async ({ page }) => {
      await page.route("**/api/auth/me", (route) => route.fulfill({ status: 401 }));
      await page.goto("/notification-channels");
      await expect(page).toHaveURL("/");
    },
  );
});

// ---------------------------------------------------------------------------
// Notification Channels page — authenticated tests
// ---------------------------------------------------------------------------

test.describe("Notification Channels page", () => {
  test("not-connected channel shows a Connect action", async ({ page }) => {
    await mockApis(page, { connectedChannels: [] });
    const notificationChannels = new NotificationChannelsPage(page);
    await notificationChannels.goto();

    await expect(notificationChannels.heading).toBeVisible();
    await expect(notificationChannels.connectButton("Telegram")).toBeVisible();
    await expect(notificationChannels.channelRow("Telegram")).toContainText(/not connected/i);
  });

  test("connected channel shows a Disconnect action", async ({ page }) => {
    await mockApis(page, { connectedChannels: ["telegram"] });
    const notificationChannels = new NotificationChannelsPage(page);
    await notificationChannels.goto();

    await expect(notificationChannels.disconnectButton("Telegram")).toBeVisible();
  });

  test(
    "connect -> preferred -> disconnect: full lifecycle clears the preference",
    async ({ page }) => {
      // Auto-connect ~1s after the link-code is issued so the test doesn't
      // need to wait out the full ~2 minute timeout the real component is
      // bounded by — this stands in for the Telegram webhook, which can't
      // be exercised in e2e.
      await mockApis(page, { connectedChannels: [], autoConnectDelayMs: 1000 });

      const notificationChannels = new NotificationChannelsPage(page);
      await notificationChannels.goto();

      await expect(notificationChannels.connectButton("Telegram")).toBeVisible();

      await notificationChannels.openConnectModal("Telegram");
      await expect(notificationChannels.deepLinkLocator()).toHaveAttribute("href", DEEP_LINK);

      // The connect-flow component polls on an interval; wait for it to
      // detect the connection and close itself.
      await expect(notificationChannels.modal).not.toBeVisible({ timeout: 10000 });
      await expect(notificationChannels.disconnectButton("Telegram")).toBeVisible();

      // Pick Telegram as the preferred channel in Preferences.
      const preferences = new PreferencesPage(page);
      await preferences.goto();
      await preferences.setPreferredChannel("Telegram");

      const [putRequest] = await Promise.all([
        page.waitForRequest(
          (req) => req.url().includes("/api/preferences") && req.method() === "PUT",
        ),
        preferences.save(),
      ]);
      expect(
        (putRequest.postDataJSON() as MockPreferences).preferred_notification_channel,
      ).toBe("telegram");
      await expect(preferences.savedMessage).toBeVisible();

      // Disconnect Telegram from the Notification Channels page.
      page.on("dialog", (dialog) => void dialog.accept());
      await notificationChannels.goto();
      await expect(notificationChannels.disconnectButton("Telegram")).toBeVisible();

      const [deleteRequest] = await Promise.all([
        page.waitForRequest(
          (req) =>
            req.url().includes("/api/notifications/channels/telegram") &&
            req.method() === "DELETE",
        ),
        notificationChannels.disconnectButton("Telegram").click(),
      ]);
      expect(deleteRequest.method()).toBe("DELETE");
      await expect(notificationChannels.connectButton("Telegram")).toBeVisible();

      // Confirm the preferred-channel preference cleared server-side.
      const [preferencesResponse] = await Promise.all([
        page.waitForResponse(
          (res) =>
            new URL(res.url()).pathname === "/api/preferences" &&
            res.request().method() === "GET",
        ),
        preferences.goto(),
      ]);
      const reloadedPreferences = (await preferencesResponse.json()) as MockPreferences;
      expect(reloadedPreferences.preferred_notification_channel).toBeNull();
      await expect(preferences.noChannelsConnectedMessage).toBeVisible();
    },
  );
});
