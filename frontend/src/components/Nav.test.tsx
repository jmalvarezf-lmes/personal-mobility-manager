import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { getMe, logout } from "../api/auth";
import i18n from "../i18n";
import { fireEvent, renderWithProviders, screen, waitFor, within } from "../test/render";
import Nav from "./Nav";

vi.mock("../api/auth");

const authenticatedUser = { id: "u1", email: "user@example.com", display_name: "User" };

async function renderAuthenticatedNav() {
  vi.mocked(getMe).mockResolvedValue(authenticatedUser);
  const result = renderWithProviders(<Nav />, { withAuth: true, withRouter: true });
  await screen.findByRole("button", { name: authenticatedUser.email });
  return result;
}

describe("Nav", () => {
  beforeEach(() => {
    vi.mocked(getMe).mockResolvedValue(null);
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it("shows the API docs link with no authenticated user, and it requires no login to click", async () => {
    renderWithProviders(<Nav />, { withAuth: true, withRouter: true });

    const link = await screen.findByRole("link", { name: "API Docs" });
    expect(link).toHaveAttribute("href", "/api-docs");
  });

  describe("authenticated account menu", () => {
    it("opens the account menu with all links present and correct hrefs, and toggles closed", async () => {
      const user = userEvent.setup();
      await renderAuthenticatedNav();

      const accountButton = screen.getByRole("button", { name: authenticatedUser.email });
      expect(accountButton).toHaveAttribute("aria-expanded", "false");

      await user.click(accountButton);

      const menu = screen.getByRole("menu", { name: "Account menu" });
      expect(accountButton).toHaveAttribute("aria-expanded", "true");
      expect(within(menu).getByRole("menuitem", { name: "My Vehicles" })).toHaveAttribute(
        "href",
        "/my-vehicles",
      );
      expect(within(menu).getByRole("menuitem", { name: "Preferences" })).toHaveAttribute(
        "href",
        "/preferences",
      );
      expect(within(menu).getByRole("menuitem", { name: "SER Providers" })).toHaveAttribute(
        "href",
        "/ser-providers",
      );
      expect(within(menu).getByRole("menuitem", { name: "Notification Channels" })).toHaveAttribute(
        "href",
        "/notification-channels",
      );
      expect(within(menu).getByRole("menuitem", { name: "Logout" })).toBeInTheDocument();

      await user.click(accountButton);

      expect(screen.queryByRole("menu", { name: "Account menu" })).not.toBeInTheDocument();
      expect(accountButton).toHaveAttribute("aria-expanded", "false");
    });

    it("closes the account menu when clicking outside of it", async () => {
      const user = userEvent.setup();
      await renderAuthenticatedNav();

      await user.click(screen.getByRole("button", { name: authenticatedUser.email }));
      expect(screen.getByRole("menu", { name: "Account menu" })).toBeInTheDocument();

      fireEvent.mouseDown(document.body);

      expect(screen.queryByRole("menu", { name: "Account menu" })).not.toBeInTheDocument();
    });

    it("closes the account menu when Escape is pressed", async () => {
      const user = userEvent.setup();
      await renderAuthenticatedNav();

      await user.click(screen.getByRole("button", { name: authenticatedUser.email }));
      expect(screen.getByRole("menu", { name: "Account menu" })).toBeInTheDocument();

      fireEvent.keyDown(document, { key: "Escape" });

      expect(screen.queryByRole("menu", { name: "Account menu" })).not.toBeInTheDocument();
    });

    it("logs out, calls the logout API, and clears the user", async () => {
      vi.mocked(logout).mockResolvedValue(undefined);
      const user = userEvent.setup();
      await renderAuthenticatedNav();

      await user.click(screen.getByRole("button", { name: authenticatedUser.email }));
      await user.click(screen.getByRole("menuitem", { name: "Logout" }));

      await waitFor(() => {
        expect(logout).toHaveBeenCalledTimes(1);
      });
      expect(await screen.findByRole("link", { name: /Login with Google/ })).toBeInTheDocument();
      expect(screen.queryByRole("button", { name: authenticatedUser.email })).not.toBeInTheDocument();
    });

    it("still clears the user when the logout API call fails", async () => {
      vi.mocked(logout).mockRejectedValue(new Error("Logout failed: 500"));
      const user = userEvent.setup();
      await renderAuthenticatedNav();

      await user.click(screen.getByRole("button", { name: authenticatedUser.email }));
      await user.click(screen.getByRole("menuitem", { name: "Logout" }));

      expect(await screen.findByRole("link", { name: /Login with Google/ })).toBeInTheDocument();
    });
  });

  describe("mobile menu", () => {
    it("toggles the mobile menu open and closed via the hamburger button", async () => {
      const user = userEvent.setup();
      renderWithProviders(<Nav />, { withAuth: true, withRouter: true });

      const menuButton = await screen.findByRole("button", { name: "Menu" });
      expect(menuButton).toHaveAttribute("aria-expanded", "false");
      expect(screen.getAllByRole("link", { name: "Map" })).toHaveLength(1);

      await user.click(menuButton);

      expect(menuButton).toHaveAttribute("aria-expanded", "true");
      expect(screen.getAllByRole("link", { name: "Map" })).toHaveLength(2);

      await user.click(menuButton);

      expect(menuButton).toHaveAttribute("aria-expanded", "false");
      expect(screen.getAllByRole("link", { name: "Map" })).toHaveLength(1);
    });

    it("closes the mobile menu when clicking outside of it", async () => {
      const user = userEvent.setup();
      renderWithProviders(<Nav />, { withAuth: true, withRouter: true });

      const menuButton = await screen.findByRole("button", { name: "Menu" });
      await user.click(menuButton);
      expect(screen.getAllByRole("link", { name: "Map" })).toHaveLength(2);

      fireEvent.mouseDown(document.body);

      expect(screen.getAllByRole("link", { name: "Map" })).toHaveLength(1);
    });
  });

  describe("language selector", () => {
    it("calls i18n.changeLanguage with the selected language", async () => {
      const changeLanguageSpy = vi.spyOn(i18n, "changeLanguage").mockResolvedValue(vi.fn() as never);
      const user = userEvent.setup();
      renderWithProviders(<Nav />, { withAuth: true, withRouter: true });

      const select = await screen.findByRole("combobox", { name: "Language" });
      await user.selectOptions(select, "es");

      expect(changeLanguageSpy).toHaveBeenCalledWith("es");
    });
  });
});
