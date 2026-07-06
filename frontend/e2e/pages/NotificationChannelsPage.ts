import type { Locator, Page } from "@playwright/test";

/**
 * Page Object Model for the /notification-channels route.
 *
 * Locator strategy:
 *  - ARIA roles / visible text for interactive elements
 *  - data-testid="notification-channel-row" required on each channel row's root element
 */
export class NotificationChannelsPage {
  readonly heading: Locator;
  readonly channelRows: Locator;
  readonly modal: Locator;

  constructor(private readonly page: Page) {
    this.heading = page.getByRole("heading", { name: "Notification Channels" });
    this.channelRows = page.locator('[data-testid="notification-channel-row"]');
    this.modal = page.getByRole("dialog");
  }

  async goto() {
    await this.page.goto("/notification-channels");
  }

  // ------------------------------------------------------------------
  // Row helpers
  // ------------------------------------------------------------------

  channelRow(displayName: string): Locator {
    return this.page.locator('[data-testid="notification-channel-row"]', { hasText: displayName });
  }

  connectButton(displayName: string): Locator {
    return this.channelRow(displayName).getByRole("button", { name: /^connect$/i });
  }

  disconnectButton(displayName: string): Locator {
    return this.channelRow(displayName).getByRole("button", { name: /^disconnect$/i });
  }

  // ------------------------------------------------------------------
  // Connect flow (modal) helpers
  // ------------------------------------------------------------------

  async openConnectModal(displayName: string) {
    await this.connectButton(displayName).click();
    await this.modal.waitFor({ state: "visible" });
  }

  deepLinkLocator(): Locator {
    return this.modal.getByRole("link");
  }

  async closeModal() {
    await this.modal.getByRole("button", { name: /close/i }).click();
  }
}
