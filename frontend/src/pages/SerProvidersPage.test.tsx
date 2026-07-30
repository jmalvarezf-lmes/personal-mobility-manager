import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { getMe } from "../api/auth";
import { connect, disconnect, getConnections } from "../api/serTicketProviders";
import { renderWithProviders, screen, waitFor, within } from "../test/render";
import SerProvidersPage from "./SerProvidersPage";

vi.mock("../api/auth");
vi.mock("../api/serTicketProviders");

async function renderPage() {
  const result = renderWithProviders(<SerProvidersPage />, { withAuth: true, withRouter: true });
  await screen.findByRole("heading", { name: "SER Providers" });
  return result;
}

describe("SerProvidersPage", () => {
  beforeEach(() => {
    vi.mocked(getMe).mockResolvedValue(null);
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it("shows a loading message while connections are being fetched", () => {
    vi.mocked(getConnections).mockReturnValue(new Promise(() => {}));
    renderWithProviders(<SerProvidersPage />, { withAuth: true, withRouter: true });

    expect(screen.getByText("Loading providers…")).toBeInTheDocument();
  });

  it("renders the known providers as not connected once loaded", async () => {
    vi.mocked(getConnections).mockResolvedValue({ providers: [] });
    await renderPage();

    expect(screen.getByRole("heading", { name: "ElParking" })).toBeInTheDocument();
    expect(screen.getByText("Not connected")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Connect" })).toBeInTheDocument();
  });

  it("shows an error message when fetching connections fails", async () => {
    vi.mocked(getConnections).mockRejectedValue(new Error("boom"));
    renderWithProviders(<SerProvidersPage />, { withAuth: true, withRouter: true });

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("boom");
  });

  it("connects a provider through the modal and marks it as connected", async () => {
    const user = userEvent.setup();
    vi.mocked(getConnections).mockResolvedValue({ providers: [] });
    vi.mocked(connect).mockResolvedValue(undefined);
    await renderPage();

    await user.click(screen.getByRole("button", { name: "Connect" }));

    const dialog = await screen.findByRole("dialog", { name: "Connect ElParking" });
    await user.type(screen.getByLabelText("Email"), "user@example.com");
    await user.type(screen.getByLabelText("Password"), "secret");
    await user.click(within(dialog).getByRole("button", { name: "Connect" }));

    await waitFor(() => {
      expect(dialog).not.toBeInTheDocument();
    });

    expect(connect).toHaveBeenCalledWith({
      provider: "elparking",
      email: "user@example.com",
      password: "secret",
    });
    expect(screen.getByText("Connected")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Disconnect" })).toBeInTheDocument();
  });

  it("shows a connect error inside the modal without closing it", async () => {
    const user = userEvent.setup();
    vi.mocked(getConnections).mockResolvedValue({ providers: [] });
    vi.mocked(connect).mockRejectedValue(new Error("Failed to connect provider."));
    await renderPage();

    await user.click(screen.getByRole("button", { name: "Connect" }));
    const dialog = await screen.findByRole("dialog", { name: "Connect ElParking" });
    await user.type(screen.getByLabelText("Email"), "user@example.com");
    await user.type(screen.getByLabelText("Password"), "secret");
    await user.click(within(dialog).getByRole("button", { name: "Connect" }));

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Failed to connect provider.");
    expect(screen.getByRole("dialog", { name: "Connect ElParking" })).toBeInTheDocument();
  });

  it("closes the modal without connecting when cancel is clicked", async () => {
    const user = userEvent.setup();
    vi.mocked(getConnections).mockResolvedValue({ providers: [] });
    await renderPage();

    await user.click(screen.getByRole("button", { name: "Connect" }));
    const dialog = await screen.findByRole("dialog", { name: "Connect ElParking" });
    await user.click(screen.getByRole("button", { name: "Cancel" }));

    expect(dialog).not.toBeInTheDocument();
    expect(connect).not.toHaveBeenCalled();
  });

  it("disconnects a connected provider after confirmation", async () => {
    const user = userEvent.setup();
    vi.mocked(getConnections).mockResolvedValue({ providers: ["elparking"] });
    vi.mocked(disconnect).mockResolvedValue({ logout_succeeded: true });
    vi.spyOn(window, "confirm").mockReturnValue(true);
    await renderPage();

    await user.click(screen.getByRole("button", { name: "Disconnect" }));

    await waitFor(() => {
      expect(screen.getByText("Not connected")).toBeInTheDocument();
    });
    expect(disconnect).toHaveBeenCalledWith("elparking");
  });

  it("does not disconnect when the confirmation dialog is dismissed", async () => {
    const user = userEvent.setup();
    vi.mocked(getConnections).mockResolvedValue({ providers: ["elparking"] });
    vi.spyOn(window, "confirm").mockReturnValue(false);
    await renderPage();

    await user.click(screen.getByRole("button", { name: "Disconnect" }));

    expect(disconnect).not.toHaveBeenCalled();
    expect(screen.getByText("Connected")).toBeInTheDocument();
  });

  it("shows a warning when the provider-side logout could not be confirmed", async () => {
    const user = userEvent.setup();
    vi.mocked(getConnections).mockResolvedValue({ providers: ["elparking"] });
    vi.mocked(disconnect).mockResolvedValue({ logout_succeeded: false });
    vi.spyOn(window, "confirm").mockReturnValue(true);
    await renderPage();

    await user.click(screen.getByRole("button", { name: "Disconnect" }));

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(
      "Disconnected, but we couldn't confirm the provider-side session was revoked.",
    );
  });
});
