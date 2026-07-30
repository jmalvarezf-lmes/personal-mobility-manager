import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { fetchToyotaLocale } from "../api/config";
import { createVehicle } from "../api/vehicles";
import { renderWithProviders, screen, waitFor } from "../test/render";
import AddVehicleModal from "./AddVehicleModal";

vi.mock("../api/config");
vi.mock("../api/vehicles");

const baseVehicle = {
  vehicle_id: "veh-1",
  brand: "generic" as const,
  display_name: "My Car",
  vin: null,
  license_plate: null,
  location: null,
  ambient_label: null,
  has_ser_tickets: false,
};

describe("AddVehicleModal", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("applies the fetched Toyota locale default once resolved", async () => {
    vi.mocked(fetchToyotaLocale).mockResolvedValue("es_ES");
    const user = userEvent.setup();
    renderWithProviders(<AddVehicleModal onClose={vi.fn()} onCreated={vi.fn()} />);

    await user.selectOptions(screen.getByLabelText("Brand"), "toyota");

    await waitFor(() => {
      expect(screen.getByLabelText("Locale")).toHaveValue("es_ES");
    });
  });

  it("renders the generic form by default without Toyota-only fields", () => {
    vi.mocked(fetchToyotaLocale).mockResolvedValue(null);
    renderWithProviders(<AddVehicleModal onClose={vi.fn()} onCreated={vi.fn()} />);

    expect(screen.getByRole("dialog", { name: "Add Vehicle" })).toBeInTheDocument();
    expect(screen.queryByLabelText("VIN")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Username")).not.toBeInTheDocument();
  });

  it("shows Toyota-only fields when the Toyota brand is selected", async () => {
    vi.mocked(fetchToyotaLocale).mockResolvedValue(null);
    const user = userEvent.setup();
    renderWithProviders(<AddVehicleModal onClose={vi.fn()} onCreated={vi.fn()} />);

    await user.selectOptions(screen.getByLabelText("Brand"), "toyota");

    expect(screen.getByLabelText("VIN")).toBeInTheDocument();
    expect(screen.getByLabelText("Username")).toBeInTheDocument();
    expect(screen.getByLabelText("Password")).toBeInTheDocument();
    expect(screen.getByLabelText("Locale")).toBeInTheDocument();
  });

  it("submits the generic payload and calls onCreated/onClose on success", async () => {
    vi.mocked(fetchToyotaLocale).mockResolvedValue(null);
    vi.mocked(createVehicle).mockResolvedValue({ ...baseVehicle, display_name: "New Car" });
    const onCreated = vi.fn();
    const onClose = vi.fn();
    const user = userEvent.setup();
    renderWithProviders(<AddVehicleModal onClose={onClose} onCreated={onCreated} />);

    await user.type(screen.getByLabelText("Display Name"), "New Car");
    await user.click(screen.getByRole("button", { name: "Add" }));

    await waitFor(() => {
      expect(createVehicle).toHaveBeenCalledWith({
        brand: "generic",
        display_name: "New Car",
        license_plate: null,
      });
    });
    expect(onCreated).toHaveBeenCalledWith({ ...baseVehicle, display_name: "New Car" });
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("submits the Toyota payload with all Toyota-specific fields", async () => {
    vi.mocked(fetchToyotaLocale).mockResolvedValue(null);
    vi.mocked(createVehicle).mockResolvedValue(baseVehicle);
    const user = userEvent.setup();
    renderWithProviders(<AddVehicleModal onClose={vi.fn()} onCreated={vi.fn()} />);

    await user.selectOptions(screen.getByLabelText("Brand"), "toyota");
    await user.type(screen.getByLabelText("Display Name"), "Toyota Car");
    await user.type(screen.getByLabelText("License Plate", { exact: false }), "1234ABC");
    await user.type(screen.getByLabelText("VIN"), "VIN123");
    await user.type(screen.getByLabelText("Username"), "myuser");
    await user.type(screen.getByLabelText("Password"), "mypass");

    await user.click(screen.getByRole("button", { name: "Add" }));

    await waitFor(() => {
      expect(createVehicle).toHaveBeenCalledWith({
        brand: "toyota",
        display_name: "Toyota Car",
        vin: "VIN123",
        username: "myuser",
        password: "mypass",
        locale: "en_GB",
        license_plate: "1234ABC",
      });
    });
  });

  it("shows an error message and keeps the modal open when submission fails", async () => {
    vi.mocked(fetchToyotaLocale).mockResolvedValue(null);
    vi.mocked(createVehicle).mockRejectedValue(new Error("Failed to create vehicle: 500"));
    const onClose = vi.fn();
    const user = userEvent.setup();
    renderWithProviders(<AddVehicleModal onClose={onClose} onCreated={vi.fn()} />);

    await user.type(screen.getByLabelText("Display Name"), "New Car");
    await user.click(screen.getByRole("button", { name: "Add" }));

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Failed to create vehicle: 500");
    expect(onClose).not.toHaveBeenCalled();
  });

  it("calls onClose without submitting when Cancel is clicked", async () => {
    vi.mocked(fetchToyotaLocale).mockResolvedValue(null);
    const onClose = vi.fn();
    const user = userEvent.setup();
    renderWithProviders(<AddVehicleModal onClose={onClose} onCreated={vi.fn()} />);

    await user.click(screen.getByRole("button", { name: "Cancel" }));

    expect(onClose).toHaveBeenCalledTimes(1);
    expect(createVehicle).not.toHaveBeenCalled();
  });
});
