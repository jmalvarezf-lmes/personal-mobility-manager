import type { Locator, Page } from "@playwright/test";

/**
 * Page Object Model for the /ser-providers route.
 *
 * Locator strategy:
 *  - ARIA roles / visible text for interactive elements
 *  - data-testid="ser-provider-row" required on each provider row's root element
 */
export class SerProvidersPage {
  readonly heading: Locator;
  readonly providerRows: Locator;
  readonly modal: Locator;

  constructor(private readonly page: Page) {
    this.heading = page.getByRole("heading", { name: "SER Providers" });
    this.providerRows = page.locator('[data-testid="ser-provider-row"]');
    this.modal = page.getByRole("dialog");
  }

  async goto() {
    await this.page.goto("/ser-providers");
  }

  // ------------------------------------------------------------------
  // Row helpers
  // ------------------------------------------------------------------

  providerRow(displayName: string): Locator {
    return this.page.locator('[data-testid="ser-provider-row"]', { hasText: displayName });
  }

  connectButton(displayName: string): Locator {
    return this.providerRow(displayName).getByRole("button", { name: /^connect$/i });
  }

  disconnectButton(displayName: string): Locator {
    return this.providerRow(displayName).getByRole("button", { name: /^disconnect$/i });
  }

  statusText(displayName: string): Locator {
    return this.providerRow(displayName);
  }

  warningMessage(displayName: string): Locator {
    return this.providerRow(displayName).getByRole("alert");
  }

  // ------------------------------------------------------------------
  // Connect modal helpers
  // ------------------------------------------------------------------

  async openConnectModal(displayName: string) {
    await this.connectButton(displayName).click();
    await this.modal.waitFor({ state: "visible" });
  }

  async fillCredentials(data: { email: string; password: string }) {
    await this.page.getByLabel(/email/i).fill(data.email);
    await this.page.getByLabel(/password/i).fill(data.password);
  }

  async submitModal() {
    await this.modal.getByRole("button", { name: /connect/i }).click();
  }

  async cancelModal() {
    await this.modal.getByRole("button", { name: /cancel/i }).click();
  }
}
