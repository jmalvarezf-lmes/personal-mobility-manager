import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { listVehicleShares, revokeVehicleShare, shareVehicle } from "../api/vehicles";
import { renderWithProviders, screen, waitFor } from "../test/render";
import ShareVehicleModal from "./ShareVehicleModal";

vi.mock("../api/vehicles");

function mockNoSharees() {
  vi.mocked(listVehicleShares).mockResolvedValue({ vehicle_id: "veh-1", sharees: [] });
}

const sharee = {
  user_id: "user-2",
  display_name: "Jane Doe",
  email: "jane@example.com",
  created_at: "2024-01-01T00:00:00Z",
};

describe("ShareVehicleModal", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("loads and displays existing sharees", async () => {
    vi.mocked(listVehicleShares).mockResolvedValue({ vehicle_id: "veh-1", sharees: [sharee] });
    renderWithProviders(<ShareVehicleModal vehicleId="veh-1" onClose={vi.fn()} />);

    await waitFor(() => {
      expect(screen.getByText("Jane Doe")).toBeInTheDocument();
    });
    expect(screen.getByText("jane@example.com")).toBeInTheDocument();
  });

  it("shows an empty state when there are no sharees", async () => {
    mockNoSharees();
    renderWithProviders(<ShareVehicleModal vehicleId="veh-1" onClose={vi.fn()} />);

    await waitFor(() => expect(listVehicleShares).toHaveBeenCalledWith("veh-1"));
    expect(screen.getByText("Not shared with anyone yet.")).toBeInTheDocument();
  });

  it("shares the vehicle by email and refreshes the sharee list", async () => {
    mockNoSharees();
    vi.mocked(shareVehicle).mockResolvedValue({ vehicle_id: "veh-1", sharees: [sharee] });
    const user = userEvent.setup();
    renderWithProviders(<ShareVehicleModal vehicleId="veh-1" onClose={vi.fn()} />);

    await waitFor(() => expect(listVehicleShares).toHaveBeenCalled());

    await user.type(screen.getByLabelText("Email"), "jane@example.com");
    await user.click(screen.getByRole("button", { name: "Share" }));

    await waitFor(() => {
      expect(shareVehicle).toHaveBeenCalledWith("veh-1", "jane@example.com");
    });
    expect(screen.getByText("Jane Doe")).toBeInTheDocument();
  });

  it("displays an error when sharing fails (unknown email)", async () => {
    mockNoSharees();
    vi.mocked(shareVehicle).mockRejectedValue(new Error("User not found"));
    const user = userEvent.setup();
    renderWithProviders(<ShareVehicleModal vehicleId="veh-1" onClose={vi.fn()} />);

    await waitFor(() => expect(listVehicleShares).toHaveBeenCalled());

    await user.type(screen.getByLabelText("Email"), "unknown@example.com");
    await user.click(screen.getByRole("button", { name: "Share" }));

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("User not found");
  });

  it("removes a sharee when the Remove button is clicked", async () => {
    vi.mocked(listVehicleShares).mockResolvedValue({ vehicle_id: "veh-1", sharees: [sharee] });
    vi.mocked(revokeVehicleShare).mockResolvedValue(undefined);
    const user = userEvent.setup();
    renderWithProviders(<ShareVehicleModal vehicleId="veh-1" onClose={vi.fn()} />);

    await waitFor(() => expect(screen.getByText("Jane Doe")).toBeInTheDocument());

    await user.click(screen.getByRole("button", { name: "Remove" }));

    await waitFor(() => {
      expect(revokeVehicleShare).toHaveBeenCalledWith("veh-1", "user-2");
    });
    expect(screen.queryByText("Jane Doe")).not.toBeInTheDocument();
  });

  it("allows a sharee to self-revoke", async () => {
    const selfSharee = { ...sharee, user_id: "me" };
    vi.mocked(listVehicleShares).mockResolvedValue({ vehicle_id: "veh-1", sharees: [selfSharee] });
    vi.mocked(revokeVehicleShare).mockResolvedValue(undefined);
    const user = userEvent.setup();
    renderWithProviders(<ShareVehicleModal vehicleId="veh-1" onClose={vi.fn()} />);

    await waitFor(() => expect(screen.getByText("Jane Doe")).toBeInTheDocument());

    await user.click(screen.getByRole("button", { name: "Remove" }));

    await waitFor(() => {
      expect(revokeVehicleShare).toHaveBeenCalledWith("veh-1", "me");
    });
  });

  it("closes when the Close button is clicked", async () => {
    mockNoSharees();
    const onClose = vi.fn();
    const user = userEvent.setup();
    renderWithProviders(<ShareVehicleModal vehicleId="veh-1" onClose={onClose} />);

    await waitFor(() => expect(listVehicleShares).toHaveBeenCalled());
    await user.click(screen.getByRole("button", { name: "Close" }));

    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
