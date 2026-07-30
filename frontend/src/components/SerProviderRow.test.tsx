import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { disconnect } from "../api/serTicketProviders";
import { fireEvent, renderWithProviders, screen, waitFor } from "../test/render";
import SerProviderRow from "./SerProviderRow";

vi.mock("../api/serTicketProviders");

describe("SerProviderRow", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("shows the not-connected state with a Connect button", () => {
    renderWithProviders(
      <SerProviderRow
        provider="elparking"
        connected={false}
        onConnect={vi.fn()}
        onDisconnected={vi.fn()}
      />,
    );

    expect(screen.getByRole("heading", { name: "ElParking" })).toBeInTheDocument();
    expect(screen.getByText("Not connected")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Connect" })).toBeInTheDocument();
  });

  it("shows the connected state with a Disconnect button", () => {
    renderWithProviders(
      <SerProviderRow
        provider="elparking"
        connected={true}
        onConnect={vi.fn()}
        onDisconnected={vi.fn()}
      />,
    );

    expect(screen.getByText("Connected")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Disconnect" })).toBeInTheDocument();
  });

  it("calls onConnect with the provider id when Connect is clicked", async () => {
    const onConnect = vi.fn();
    const user = userEvent.setup();
    renderWithProviders(
      <SerProviderRow
        provider="elparking"
        connected={false}
        onConnect={onConnect}
        onDisconnected={vi.fn()}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Connect" }));

    expect(onConnect).toHaveBeenCalledWith("elparking");
  });

  it("disconnects after confirmation and calls onDisconnected", async () => {
    vi.mocked(disconnect).mockResolvedValue({ logout_succeeded: true });
    vi.spyOn(window, "confirm").mockReturnValue(true);
    const onDisconnected = vi.fn();
    const user = userEvent.setup();
    renderWithProviders(
      <SerProviderRow
        provider="elparking"
        connected={true}
        onConnect={vi.fn()}
        onDisconnected={onDisconnected}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Disconnect" }));

    await waitFor(() => {
      expect(disconnect).toHaveBeenCalledWith("elparking");
    });
    expect(onDisconnected).toHaveBeenCalledWith("elparking", true);
  });

  it("does not disconnect when the confirmation is dismissed", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(false);
    const onDisconnected = vi.fn();
    const user = userEvent.setup();
    renderWithProviders(
      <SerProviderRow
        provider="elparking"
        connected={true}
        onConnect={vi.fn()}
        onDisconnected={onDisconnected}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Disconnect" }));

    expect(disconnect).not.toHaveBeenCalled();
    expect(onDisconnected).not.toHaveBeenCalled();
  });

  it("shows a warning when the provider-side logout could not be confirmed", async () => {
    vi.mocked(disconnect).mockResolvedValue({ logout_succeeded: false });
    vi.spyOn(window, "confirm").mockReturnValue(true);
    const user = userEvent.setup();
    renderWithProviders(
      <SerProviderRow
        provider="elparking"
        connected={true}
        onConnect={vi.fn()}
        onDisconnected={vi.fn()}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Disconnect" }));

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(
      "Disconnected, but we couldn't confirm the provider-side session was revoked.",
    );
  });

  it("shows an error message when disconnect fails", async () => {
    vi.mocked(disconnect).mockRejectedValue(new Error("Failed to disconnect provider: 500"));
    vi.spyOn(window, "confirm").mockReturnValue(true);
    const user = userEvent.setup();
    renderWithProviders(
      <SerProviderRow
        provider="elparking"
        connected={true}
        onConnect={vi.fn()}
        onDisconnected={vi.fn()}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Disconnect" }));

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Failed to disconnect provider: 500");
  });

  it("hides the logo image after it fails to load", () => {
    const { container } = renderWithProviders(
      <SerProviderRow
        provider="elparking"
        connected={false}
        onConnect={vi.fn()}
        onDisconnected={vi.fn()}
      />,
    );

    const img = container.querySelector("img");
    expect(img).not.toBeNull();

    fireEvent.error(img!);

    expect(container.querySelector("img")).toBeNull();
  });
});
