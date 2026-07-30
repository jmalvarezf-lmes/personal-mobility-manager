import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { disconnectChannel } from "../../api/notifications";
import { renderWithProviders, screen, waitFor } from "../../test/render";
import NotificationChannelRow from "./NotificationChannelRow";

vi.mock("../../api/notifications");

describe("NotificationChannelRow", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("shows the not-connected state with an enabled Connect button when supported", () => {
    renderWithProviders(
      <NotificationChannelRow
        channel="telegram"
        connected={false}
        supported={true}
        onConnect={vi.fn()}
        onDisconnected={vi.fn()}
      />,
    );

    expect(screen.getByRole("heading", { name: "Telegram" })).toBeInTheDocument();
    expect(screen.getByText("Not connected")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Connect" })).toBeEnabled();
  });

  it("shows the not-supported message and disables Connect when unsupported", () => {
    renderWithProviders(
      <NotificationChannelRow
        channel="sms"
        connected={false}
        supported={false}
        onConnect={vi.fn()}
        onDisconnected={vi.fn()}
      />,
    );

    expect(screen.getByText("Not yet supported")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Connect" })).toBeDisabled();
  });

  it("shows the connected state with a Disconnect button", () => {
    renderWithProviders(
      <NotificationChannelRow
        channel="telegram"
        connected={true}
        supported={true}
        onConnect={vi.fn()}
        onDisconnected={vi.fn()}
      />,
    );

    expect(screen.getByText("Connected")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Disconnect" })).toBeInTheDocument();
  });

  it("calls onConnect with the channel id when Connect is clicked", async () => {
    const onConnect = vi.fn();
    const user = userEvent.setup();
    renderWithProviders(
      <NotificationChannelRow
        channel="telegram"
        connected={false}
        supported={true}
        onConnect={onConnect}
        onDisconnected={vi.fn()}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Connect" }));

    expect(onConnect).toHaveBeenCalledWith("telegram");
  });

  it("disconnects after confirmation and calls onDisconnected", async () => {
    vi.mocked(disconnectChannel).mockResolvedValue(undefined);
    vi.spyOn(window, "confirm").mockReturnValue(true);
    const onDisconnected = vi.fn();
    const user = userEvent.setup();
    renderWithProviders(
      <NotificationChannelRow
        channel="telegram"
        connected={true}
        supported={true}
        onConnect={vi.fn()}
        onDisconnected={onDisconnected}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Disconnect" }));

    await waitFor(() => {
      expect(disconnectChannel).toHaveBeenCalledWith("telegram");
    });
    expect(onDisconnected).toHaveBeenCalledWith("telegram");
  });

  it("does not disconnect when the confirmation is dismissed", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(false);
    const onDisconnected = vi.fn();
    const user = userEvent.setup();
    renderWithProviders(
      <NotificationChannelRow
        channel="telegram"
        connected={true}
        supported={true}
        onConnect={vi.fn()}
        onDisconnected={onDisconnected}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Disconnect" }));

    expect(disconnectChannel).not.toHaveBeenCalled();
    expect(onDisconnected).not.toHaveBeenCalled();
  });

  it("shows an error message when disconnect fails", async () => {
    vi.mocked(disconnectChannel).mockRejectedValue(new Error("Failed to disconnect channel: 500"));
    vi.spyOn(window, "confirm").mockReturnValue(true);
    const user = userEvent.setup();
    renderWithProviders(
      <NotificationChannelRow
        channel="telegram"
        connected={true}
        supported={true}
        onConnect={vi.fn()}
        onDisconnected={vi.fn()}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Disconnect" }));

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Failed to disconnect channel: 500");
  });
});
