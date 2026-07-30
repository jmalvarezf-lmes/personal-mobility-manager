import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { connect } from "../api/serTicketProviders";
import { renderWithProviders, screen, waitFor } from "../test/render";
import ConnectSerProviderModal from "./ConnectSerProviderModal";

vi.mock("../api/serTicketProviders");

describe("ConnectSerProviderModal", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("renders the dialog titled with the given provider display name", () => {
    renderWithProviders(
      <ConnectSerProviderModal
        provider="elparking"
        providerDisplayName="ElParking"
        onClose={vi.fn()}
        onConnected={vi.fn()}
      />,
    );

    expect(screen.getByRole("dialog", { name: "Connect ElParking" })).toBeInTheDocument();
  });

  it("submits the entered credentials and calls onConnected/onClose on success", async () => {
    vi.mocked(connect).mockResolvedValue(undefined);
    const onConnected = vi.fn();
    const onClose = vi.fn();
    const user = userEvent.setup();
    renderWithProviders(
      <ConnectSerProviderModal
        provider="elparking"
        providerDisplayName="ElParking"
        onClose={onClose}
        onConnected={onConnected}
      />,
    );

    await user.type(screen.getByLabelText("Email"), "user@example.com");
    await user.type(screen.getByLabelText("Password"), "secret");
    await user.click(screen.getByRole("button", { name: "Connect" }));

    await waitFor(() => {
      expect(connect).toHaveBeenCalledWith({
        provider: "elparking",
        email: "user@example.com",
        password: "secret",
      });
    });
    expect(onConnected).toHaveBeenCalledWith("elparking");
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("shows an error and keeps the modal open when the connect call fails", async () => {
    vi.mocked(connect).mockRejectedValue(new Error("Failed to connect provider."));
    const onClose = vi.fn();
    const user = userEvent.setup();
    renderWithProviders(
      <ConnectSerProviderModal
        provider="elparking"
        providerDisplayName="ElParking"
        onClose={onClose}
        onConnected={vi.fn()}
      />,
    );

    await user.type(screen.getByLabelText("Email"), "user@example.com");
    await user.type(screen.getByLabelText("Password"), "secret");
    await user.click(screen.getByRole("button", { name: "Connect" }));

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Failed to connect provider.");
    expect(onClose).not.toHaveBeenCalled();
  });

  it("calls onClose without connecting when Cancel is clicked", async () => {
    const onClose = vi.fn();
    const user = userEvent.setup();
    renderWithProviders(
      <ConnectSerProviderModal
        provider="elparking"
        providerDisplayName="ElParking"
        onClose={onClose}
        onConnected={vi.fn()}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Cancel" }));

    expect(onClose).toHaveBeenCalledTimes(1);
    expect(connect).not.toHaveBeenCalled();
  });
});
