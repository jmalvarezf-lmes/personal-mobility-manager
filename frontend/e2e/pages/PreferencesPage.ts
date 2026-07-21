import type { Locator, Page } from "@playwright/test";

/**
 * Page Object Model for the /preferences route.
 *
 * Locator strategy:
 *  - ARIA roles / labels for interactive elements (number input, checkbox, save button)
 *  - role="alert" for the error message
 *  - Notification-type rows (toggle + inline config field) are looked up by
 *    the type's `key` via id, since multiple types can share the same field
 *    label (e.g. both catalog types expose "threshold_m"), which would make
 *    `getByLabel` ambiguous across rows.
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
  readonly timezoneSearchInput: Locator;
  readonly clearTimezoneButton: Locator;

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
    this.timezoneSearchInput = page.getByRole("combobox", { name: /^timezone$/i });
    this.clearTimezoneButton = page.getByRole("button", { name: /^clear$/i });
  }

  notificationToggle(typeKey: string): Locator {
    return this.page.locator(`#notification-${typeKey}-enabled`);
  }

  notificationThresholdInput(typeKey: string): Locator {
    return this.page.locator(`#notification-${typeKey}-threshold_m`);
  }

  async setNotificationEnabled(typeKey: string, value: boolean) {
    const toggle = this.notificationToggle(typeKey);
    const checked = await toggle.isChecked();
    if (checked !== value) {
      await toggle.click();
    }
  }

  async setNotificationThreshold(typeKey: string, meters: number) {
    await this.notificationThresholdInput(typeKey).fill(String(meters));
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

  async searchTimezone(term: string) {
    await this.timezoneSearchInput.fill(term);
  }

  async setTimezone(zoneValue: string) {
    await this.timezoneSearchInput.fill(zoneValue);
    // Option labels are "<Zone> (<abbreviation>)" — anchor to the start and
    // require the zone id to be immediately followed by " (" so a zone id
    // that happens to be a prefix of another (e.g. "America/Indiana" vs.
    // "America/Indiana/Indianapolis") can't match the wrong option.
    const escaped = zoneValue.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    await this.page.getByRole("option", { name: new RegExp(`^${escaped} \\(`) }).click();
  }

  async clearTimezone() {
    await this.clearTimezoneButton.click();
  }

  async save() {
    await this.saveButton.click();
  }
}
