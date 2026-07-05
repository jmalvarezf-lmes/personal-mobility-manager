import { expect, test as base, type Page } from "@playwright/test";
import { test } from "./fixtures/auth";
import { SerProvidersPage } from "./pages/SerProvidersPage";

// ---------------------------------------------------------------------------
// Route mock helper
// ---------------------------------------------------------------------------

/**
 * Wires up GET/POST/DELETE /api/ser-ticket-providers/connections* route
 * handlers for a given test page. `connectedProviders` is mutated in-place
 * by POST/DELETE so GET always reflects the current state within the same
 * test without re-routing.
 */
async function mockSerProviderApis(
  page: Page,
  options: {
    connectedProviders?: string[];
    logoutSucceeded?: boolean;
  } = {},
) {
  const connectedProviders = options.connectedProviders ?? [];
  const logoutSucceeded = options.logoutSucceeded ?? true;

  await page.route("**/api/ser-ticket-providers/connections", async (route, request) => {
    const method = request.method();
    if (method === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ providers: connectedProviders }),
      });
    } else if (method === "POST") {
      const body = (await request.postDataJSON()) as { provider: string };
      if (!connectedProviders.includes(body.provider)) {
        connectedProviders.push(body.provider);
      }
      await route.fulfill({ status: 204 });
    }
  });

  await page.route("**/api/ser-ticket-providers/connections/*", async (route, request) => {
    if (request.method() === "DELETE") {
      const provider = request.url().split("/").pop()!;
      const idx = connectedProviders.indexOf(provider);
      if (idx !== -1) connectedProviders.splice(idx, 1);
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ logout_succeeded: logoutSucceeded }),
      });
    }
  });
}

// ---------------------------------------------------------------------------
// Auth guard — unauthenticated scenarios use the base test (no auth mock)
// ---------------------------------------------------------------------------

base.describe("Auth guard", () => {
  base("unauthenticated user is redirected from /ser-providers to /", async ({ page }) => {
    await page.route("**/api/auth/me", (route) => route.fulfill({ status: 401 }));
    await page.goto("/ser-providers");
    await expect(page).toHaveURL("/");
  });
});

// ---------------------------------------------------------------------------
// SER Providers page — authenticated tests
// ---------------------------------------------------------------------------

test.describe("SER Providers page", () => {
  test("not-connected provider shows a Connect action", async ({ page }) => {
    await mockSerProviderApis(page, { connectedProviders: [] });
    const serProviders = new SerProvidersPage(page);
    await serProviders.goto();

    await expect(serProviders.heading).toBeVisible();
    await expect(serProviders.connectButton("ElParking")).toBeVisible();
    await expect(serProviders.providerRow("ElParking")).toContainText(/not connected/i);
  });

  test("connecting a provider updates status without a manual refresh", async ({ page }) => {
    await mockSerProviderApis(page, { connectedProviders: [] });
    const serProviders = new SerProvidersPage(page);
    await serProviders.goto();

    await serProviders.openConnectModal("ElParking");
    await serProviders.fillCredentials({ email: "user@example.com", password: "secret" });

    const [postRequest] = await Promise.all([
      page.waitForRequest(
        (req) =>
          req.url().includes("/api/ser-ticket-providers/connections") &&
          req.method() === "POST",
      ),
      serProviders.submitModal(),
    ]);

    const body = postRequest.postDataJSON() as {
      provider: string;
      email: string;
      password: string;
    };
    expect(body.provider).toBe("elparking");
    expect(body.email).toBe("user@example.com");

    await expect(serProviders.modal).not.toBeVisible();
    await expect(serProviders.providerRow("ElParking").getByText("Connected", { exact: true })).toBeVisible();
    await expect(serProviders.disconnectButton("ElParking")).toBeVisible();
  });

  test("connected provider shows a Disconnect action", async ({ page }) => {
    await mockSerProviderApis(page, { connectedProviders: ["elparking"] });
    const serProviders = new SerProvidersPage(page);
    await serProviders.goto();

    await expect(serProviders.disconnectButton("ElParking")).toBeVisible();
  });

  test("disconnecting with logout_succeeded true removes connected status cleanly", async ({
    page,
  }) => {
    await mockSerProviderApis(page, {
      connectedProviders: ["elparking"],
      logoutSucceeded: true,
    });
    page.on("dialog", (dialog) => void dialog.accept());

    const serProviders = new SerProvidersPage(page);
    await serProviders.goto();

    const [deleteRequest] = await Promise.all([
      page.waitForRequest(
        (req) =>
          req.url().includes("/api/ser-ticket-providers/connections/elparking") &&
          req.method() === "DELETE",
      ),
      serProviders.disconnectButton("ElParking").click(),
    ]);

    expect(deleteRequest.method()).toBe("DELETE");
    await expect(serProviders.connectButton("ElParking")).toBeVisible();
    await expect(serProviders.providerRow("ElParking").getByRole("alert")).not.toBeVisible();
  });

  test("disconnecting with logout_succeeded false still shows disconnected plus a warning", async ({
    page,
  }) => {
    await mockSerProviderApis(page, {
      connectedProviders: ["elparking"],
      logoutSucceeded: false,
    });
    page.on("dialog", (dialog) => void dialog.accept());

    const serProviders = new SerProvidersPage(page);
    await serProviders.goto();

    await serProviders.disconnectButton("ElParking").click();

    await expect(serProviders.connectButton("ElParking")).toBeVisible();
    await expect(serProviders.warningMessage("ElParking")).toBeVisible();
  });

  test("cancelling the disconnect confirmation leaves the connection intact", async ({
    page,
  }) => {
    await mockSerProviderApis(page, { connectedProviders: ["elparking"] });
    let deleteCalled = false;
    page.on("request", (req) => {
      if (req.method() === "DELETE") deleteCalled = true;
    });
    page.on("dialog", (dialog) => void dialog.dismiss());

    const serProviders = new SerProvidersPage(page);
    await serProviders.goto();
    await serProviders.disconnectButton("ElParking").click();

    await expect(serProviders.disconnectButton("ElParking")).toBeVisible();
    expect(deleteCalled).toBe(false);
  });
});
