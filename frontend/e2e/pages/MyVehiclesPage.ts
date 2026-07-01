import type { Locator, Page } from "@playwright/test";

/**
 * Page Object Model for the /my-vehicles route.
 *
 * Locator strategy:
 *  - ARIA roles / visible text for interactive elements
 *  - data-testid="vehicle-card" required on each card root element
 *  - .leaflet-container / .leaflet-marker-icon for map assertions
 */
export class MyVehiclesPage {
  readonly heading: Locator;
  readonly addVehicleButton: Locator;
  readonly map: Locator;
  readonly vehicleCards: Locator;
  readonly modal: Locator;

  constructor(private readonly page: Page) {
    this.heading = page.getByRole("heading", { name: "My Vehicles" });
    this.addVehicleButton = page.getByRole("button", { name: /add vehicle/i });
    this.map = page.locator(".leaflet-container");
    this.vehicleCards = page.locator('[data-testid="vehicle-card"]');
    this.modal = page.getByRole("dialog");
  }

  async goto() {
    await this.page.goto("/my-vehicles");
  }

  // ------------------------------------------------------------------
  // Card helpers
  // ------------------------------------------------------------------

  vehicleCard(displayName: string): Locator {
    return this.page.locator('[data-testid="vehicle-card"]', { hasText: displayName });
  }

  editButton(displayName: string): Locator {
    return this.vehicleCard(displayName).getByRole("button", { name: /edit/i });
  }

  deleteButton(displayName: string): Locator {
    return this.vehicleCard(displayName).getByRole("button", { name: /delete/i });
  }

  // ------------------------------------------------------------------
  // Add modal helpers
  // ------------------------------------------------------------------

  async openAddModal() {
    await this.addVehicleButton.click();
    await this.modal.waitFor({ state: "visible" });
  }

  async selectBrand(brand: "toyota" | "generic") {
    await this.page.getByLabel(/brand/i).selectOption(brand);
  }

  async fillToyotaFields(data: {
    displayName: string;
    vin: string;
    username: string;
    password: string;
    locale: string;
  }) {
    await this.page.getByLabel(/display name/i).fill(data.displayName);
    await this.page.getByLabel(/vin/i).fill(data.vin);
    await this.page.getByLabel(/username/i).fill(data.username);
    await this.page.getByLabel(/password/i).fill(data.password);
    await this.page.getByLabel(/locale/i).fill(data.locale);
  }

  async fillGenericFields(data: { displayName: string }) {
    await this.page.getByLabel(/display name/i).fill(data.displayName);
  }

  async submitModal() {
    await this.modal.getByRole("button", { name: /save|create|add/i }).click();
  }

  async cancelModal() {
    await this.modal.getByRole("button", { name: /cancel/i }).click();
  }

  // ------------------------------------------------------------------
  // Edit modal helpers
  // ------------------------------------------------------------------

  async openEditModal(displayName: string) {
    await this.editButton(displayName).click();
    await this.modal.waitFor({ state: "visible" });
  }

  get modalDisplayNameInput(): Locator {
    return this.modal.getByLabel(/display name/i);
  }

  get modalPasswordInput(): Locator {
    return this.modal.getByLabel(/password/i);
  }

  // ------------------------------------------------------------------
  // Map helpers
  // ------------------------------------------------------------------

  get carMarkers(): Locator {
    return this.page.locator(".leaflet-marker-icon");
  }
}
