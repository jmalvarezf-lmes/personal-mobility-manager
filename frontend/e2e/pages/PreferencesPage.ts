import type { Locator, Page } from "@playwright/test";

/**
 * Page Object Model for the /preferences route.
 *
 * Locator strategy:
 *  - ARIA roles / labels for interactive elements (number input, checkbox, save button)
 *  - role="alert" for the error message
 */
export class PreferencesPage {
  readonly heading: Locator;
  readonly durationInput: Locator;
  readonly autoCreateCheckbox: Locator;
  readonly saveButton: Locator;
  readonly errorMessage: Locator;
  readonly savedMessage: Locator;
  readonly preferredChannelSelect: Locator;
  readonly noChannelsConnectedMessage: Locator;
  readonly notificationLanguageSelect: Locator;

  constructor(private readonly page: Page) {
    this.heading = page.getByRole("heading", { name: "Preferences" });
    this.durationInput = page.getByLabel(/default ticket duration/i);
    this.autoCreateCheckbox = page.getByLabel(/automatically create tickets/i);
    this.saveButton = page.getByRole("button", { name: /^save$/i });
    this.errorMessage = page.getByRole("alert");
    this.savedMessage = page.getByText(/preferences saved/i);
    this.preferredChannelSelect = page.getByLabel(/preferred notification channel/i);
    this.noChannelsConnectedMessage = page.getByText(/connect a notification channel/i);
    this.notificationLanguageSelect = page.getByLabel(/notification language/i);
  }

  async goto() {
    await this.page.goto("/preferences");
  }

  async setDuration(minutes: number) {
    await this.durationInput.fill(String(minutes));
  }

  async setAutoCreate(value: boolean) {
    const checked = await this.autoCreateCheckbox.isChecked();
    if (checked !== value) {
      await this.autoCreateCheckbox.click();
    }
  }

  async setPreferredChannel(displayName: string) {
    await this.preferredChannelSelect.selectOption({ label: displayName });
  }

  async setNotificationLanguage(displayName: string) {
    await this.notificationLanguageSelect.selectOption({ label: displayName });
  }

  async save() {
    await this.saveButton.click();
  }
}
