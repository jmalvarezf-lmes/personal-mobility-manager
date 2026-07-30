import { afterEach, describe, expect, it, vi } from "vitest";

import { createTelegramLinkCode, getConfiguredChannels } from "../../api/notifications";
import { act, renderWithProviders, screen } from "../../test/render";
import TelegramConnectFlow from "./TelegramConnectFlow";

vi.mock("../../api/notifications");

const DEEP_LINK = "https://t.me/mobility_bot?start=abc123";

describe("TelegramConnectFlow", () => {
  afterEach(() => {
    vi.useRealTimers();
    vi.clearAllMocks();
  });

  it("shows the generating-link message, then the deep link once resolved", async () => {
    vi.useFakeTimers();
    vi.mocked(createTelegramLinkCode).mockResolvedValue({ deep_link: DEEP_LINK });

    renderWithProviders(<TelegramConnectFlow onClose={vi.fn()} onConnected={vi.fn()} />);

    expect(screen.getByText("Generating link…")).toBeInTheDocument();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });

    expect(screen.getByRole("link", { name: DEEP_LINK })).toHaveAttribute("href", DEEP_LINK);
    expect(screen.getByText("Waiting for confirmation…")).toBeInTheDocument();
  });

  it("shows an error message when creating the link code fails", async () => {
    vi.useFakeTimers();
    vi.mocked(createTelegramLinkCode).mockRejectedValue(
      new Error("Failed to create Telegram link code: 500"),
    );

    renderWithProviders(<TelegramConnectFlow onClose={vi.fn()} onConnected={vi.fn()} />);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });

    expect(screen.getByRole("alert")).toHaveTextContent("Failed to create Telegram link code: 500");
    expect(screen.queryByText("Generating link…")).not.toBeInTheDocument();
  });

  it("calls onClose when the close button is clicked", async () => {
    vi.mocked(createTelegramLinkCode).mockResolvedValue({ deep_link: DEEP_LINK });
    const onClose = vi.fn();

    renderWithProviders(<TelegramConnectFlow onClose={onClose} onConnected={vi.fn()} />);

    (await screen.findByRole("button", { name: "Close" })).click();

    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("stops polling and reports the connection once the channel becomes configured", async () => {
    vi.useFakeTimers();
    vi.mocked(createTelegramLinkCode).mockResolvedValue({ deep_link: DEEP_LINK });
    vi.mocked(getConfiguredChannels).mockResolvedValue({ channels: ["telegram"] });
    const onConnected = vi.fn();
    const onClose = vi.fn();

    renderWithProviders(<TelegramConnectFlow onClose={onClose} onConnected={onConnected} />);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(3000);
    });

    expect(getConfiguredChannels).toHaveBeenCalled();
    expect(onConnected).toHaveBeenCalledWith("telegram");
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("keeps polling silently through transient errors without timing out early", async () => {
    vi.useFakeTimers();
    vi.mocked(createTelegramLinkCode).mockResolvedValue({ deep_link: DEEP_LINK });
    vi.mocked(getConfiguredChannels).mockRejectedValue(new Error("network blip"));
    const onConnected = vi.fn();

    renderWithProviders(<TelegramConnectFlow onClose={vi.fn()} onConnected={onConnected} />);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(3000);
    });

    expect(getConfiguredChannels).toHaveBeenCalled();
    expect(onConnected).not.toHaveBeenCalled();
    expect(screen.queryByText(/still waiting/i)).not.toBeInTheDocument();
  });

  it("shows a still-waiting message after exhausting all poll attempts", async () => {
    vi.useFakeTimers();
    vi.mocked(createTelegramLinkCode).mockResolvedValue({ deep_link: DEEP_LINK });
    vi.mocked(getConfiguredChannels).mockResolvedValue({ channels: [] });
    const onConnected = vi.fn();
    const onClose = vi.fn();

    renderWithProviders(<TelegramConnectFlow onClose={onClose} onConnected={onConnected} />);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(3000 * 40);
    });

    expect(screen.getByText("Still waiting — you can close this and check back later.")).toBeInTheDocument();
    expect(onConnected).not.toHaveBeenCalled();
    expect(onClose).not.toHaveBeenCalled();
  });
});
