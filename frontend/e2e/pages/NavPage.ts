import type { Locator, Page } from "@playwright/test";

/**
 * Page Object Model for the logged-in account dropdown in `Nav.tsx`.
 *
 * Locator strategy:
 *  - The trigger is the button showing the user's email, exposed with
 *    `aria-haspopup`/`aria-expanded`.
 *  - The menu itself uses `role="menu"`, items use `role="menuitem"`, so
 *    everything is targetable via `getByRole` without ad-hoc data-testids.
 */
export class NavPage {
  readonly menu: Locator;
  readonly myVehiclesLink: Locator;
  readonly preferencesLink: Locator;
  readonly serProvidersLink: Locator;
  readonly logoutButton: Locator;

  constructor(
    private readonly page: Page,
    private readonly email: string,
  ) {
    this.menu = page.getByRole("menu");
    this.myVehiclesLink = this.menu.getByRole("menuitem", { name: "My Vehicles" });
    this.preferencesLink = this.menu.getByRole("menuitem", { name: "Preferences" });
    this.serProvidersLink = this.menu.getByRole("menuitem", { name: "SER Providers" });
    this.logoutButton = this.menu.getByRole("menuitem", { name: "Logout" });
  }

  get accountTrigger(): Locator {
    return this.page.getByRole("button", { name: this.email });
  }

  async open() {
    await this.accountTrigger.click();
    await this.menu.waitFor({ state: "visible" });
  }
}
