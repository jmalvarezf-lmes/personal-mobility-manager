import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { getMe } from "../api/auth";
import {
  createTelegramLinkCode,
  disconnectChannel,
  getAvailableChannels,
  getConfiguredChannels,
} from "../api/notifications";
import { renderWithProviders, screen, waitFor } from "../test/render";
import NotificationChannelsPage from "./NotificationChannelsPage";

vi.mock("../api/auth");
vi.mock("../api/notifications");

async function renderPage() {
  const result = renderWithProviders(<NotificationChannelsPage />, {
    withAuth: true,
    withRouter: true,
  });
  await screen.findByRole("heading", { name: "Notification Channels" });
  return result;
}

describe("NotificationChannelsPage", () => {
  beforeEach(() => {
    vi.mocked(getMe).mockResolvedValue(null);
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it("shows a loading message while channels are being fetched", () => {
    vi.mocked(getAvailableChannels).mockReturnValue(new Promise(() => {}));
    vi.mocked(getConfiguredChannels).mockReturnValue(new Promise(() => {}));
    renderWithProviders(<NotificationChannelsPage />, { withAuth: true, withRouter: true });

    expect(screen.getByText("Loading notification channels…")).toBeInTheDocument();
  });

  it("renders a supported channel as not connected once loaded", async () => {
    vi.mocked(getAvailableChannels).mockResolvedValue({ channels: ["telegram"] });
    vi.mocked(getConfiguredChannels).mockResolvedValue({ channels: [] });
    await renderPage();

    expect(screen.getByRole("heading", { name: "Telegram" })).toBeInTheDocument();
    expect(screen.getByText("Not connected")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Connect" })).toBeEnabled();
  });

  it("disables connect for a channel with no registered connect flow", async () => {
    vi.mocked(getAvailableChannels).mockResolvedValue({ channels: ["sms"] });
    vi.mocked(getConfiguredChannels).mockResolvedValue({ channels: [] });
    await renderPage();

    expect(screen.getByText("Not yet supported")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Connect" })).toBeDisabled();
  });

  it("shows an error message when fetching channels fails", async () => {
    vi.mocked(getAvailableChannels).mockRejectedValue(new Error("boom"));
    vi.mocked(getConfiguredChannels).mockResolvedValue({ channels: [] });
    renderWithProviders(<NotificationChannelsPage />, { withAuth: true, withRouter: true });

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("boom");
  });

  it("opens the Telegram connect flow modal and closes it", async () => {
    const user = userEvent.setup();
    vi.mocked(getAvailableChannels).mockResolvedValue({ channels: ["telegram"] });
    vi.mocked(getConfiguredChannels).mockResolvedValue({ channels: [] });
    vi.mocked(createTelegramLinkCode).mockResolvedValue({ deep_link: "tg://link" });
    await renderPage();

    await user.click(screen.getByRole("button", { name: "Connect" }));

    const dialog = await screen.findByRole("dialog", { name: "Connect Telegram" });
    await screen.findByText("tg://link");

    await user.click(screen.getByRole("button", { name: "Close" }));
    expect(dialog).not.toBeInTheDocument();
  });

  it("disconnects a connected channel after confirmation", async () => {
    const user = userEvent.setup();
    vi.mocked(getAvailableChannels).mockResolvedValue({ channels: ["telegram"] });
    vi.mocked(getConfiguredChannels).mockResolvedValue({ channels: ["telegram"] });
    vi.mocked(disconnectChannel).mockResolvedValue(undefined);
    vi.spyOn(window, "confirm").mockReturnValue(true);
    await renderPage();

    await user.click(screen.getByRole("button", { name: "Disconnect" }));

    await waitFor(() => {
      expect(screen.getByText("Not connected")).toBeInTheDocument();
    });
    expect(disconnectChannel).toHaveBeenCalledWith("telegram");
  });

  it("does not disconnect when the confirmation dialog is dismissed", async () => {
    const user = userEvent.setup();
    vi.mocked(getAvailableChannels).mockResolvedValue({ channels: ["telegram"] });
    vi.mocked(getConfiguredChannels).mockResolvedValue({ channels: ["telegram"] });
    vi.spyOn(window, "confirm").mockReturnValue(false);
    await renderPage();

    await user.click(screen.getByRole("button", { name: "Disconnect" }));

    expect(disconnectChannel).not.toHaveBeenCalled();
    expect(screen.getByText("Connected")).toBeInTheDocument();
  });

  it("shows an error when disconnecting a channel fails", async () => {
    const user = userEvent.setup();
    vi.mocked(getAvailableChannels).mockResolvedValue({ channels: ["telegram"] });
    vi.mocked(getConfiguredChannels).mockResolvedValue({ channels: ["telegram"] });
    vi.mocked(disconnectChannel).mockRejectedValue(new Error("Failed to disconnect channel."));
    vi.spyOn(window, "confirm").mockReturnValue(true);
    await renderPage();

    await user.click(screen.getByRole("button", { name: "Disconnect" }));

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Failed to disconnect channel.");
  });
});
