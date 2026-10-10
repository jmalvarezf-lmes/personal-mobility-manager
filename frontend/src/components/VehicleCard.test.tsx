import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { getVehicle, listVehicleShares, pushVehicleLocation } from "../api/vehicles";
import type { VehicleListItem, VehicleLocation } from "../types/vehicle";
import { renderWithProviders, screen, waitFor } from "../test/render";
import VehicleCard from "./VehicleCard";

vi.mock("../api/vehicles");

/**
 * Mirrors how MyVehiclesPage wires `onLocationUpdated` into vehicle-list
 * state, so the full round trip through the real (non-mocked)
 * SetVehicleLocationModal can be exercised end to end.
 */
function VehicleCardWithLocationState({ vehicle: initial }: { vehicle: VehicleListItem }) {
  const [vehicle, setVehicle] = useState(initial);
  return (
    <VehicleCard
      vehicle={vehicle}
      onEdit={noop}
      onDeleted={noop}
      onViewHistory={noop}
      onViewSerTickets={noop}
      onLocationUpdated={(_vehicleId: string, location: VehicleLocation) =>
        setVehicle((v) => ({ ...v, location }))
      }
    />
  );
}

function makeVehicle(overrides: Partial<VehicleListItem> = {}): VehicleListItem {
  return {
    vehicle_id: "1",
    brand: "generic",
    display_name: "My scooter",
    vin: null,
    license_plate: null,
    location: null,
    ambient_label: null,
    has_ser_tickets: false,
    is_owner: true,
    ...overrides,
  };
}

const noop = () => undefined;

describe("VehicleCard ambient label rendering", () => {
  beforeEach(() => {
    vi.mocked(getVehicle).mockResolvedValue({
      vehicle_id: "1",
      brand: "generic",
      display_name: "My scooter",
      vin: null,
      license_plate: null,
      config: { location_token: "tok" },
      ambient_label: null,
      is_owner: true,
    });
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it("renders the ambient label icon for a vehicle with a resolved label", () => {
    const vehicle = makeVehicle({ ambient_label: "B" });
    renderWithProviders(
      <VehicleCard
        vehicle={vehicle}
        onEdit={noop}
        onDeleted={noop}
        onViewHistory={noop}
        onViewSerTickets={noop}
      />,
    );

    const icon = screen.getByRole("img", { name: "Ambient label B" });
    expect(icon).toHaveAttribute("src", "/api/ambient-labels/B/icon");
  });

  it("renders the 'no label' indicator for a vehicle in category A", () => {
    const vehicle = makeVehicle({ ambient_label: "A" });
    renderWithProviders(
      <VehicleCard
        vehicle={vehicle}
        onEdit={noop}
        onDeleted={noop}
        onViewHistory={noop}
        onViewSerTickets={noop}
      />,
    );

    expect(screen.getByTestId("ambient-label-none")).toHaveTextContent("No label");
  });

  it("renders no ambient-label element for a vehicle with a null ambient label", () => {
    const vehicle = makeVehicle({ ambient_label: null });
    renderWithProviders(
      <VehicleCard
        vehicle={vehicle}
        onEdit={noop}
        onDeleted={noop}
        onViewHistory={noop}
        onViewSerTickets={noop}
      />,
    );

    expect(screen.queryByRole("img", { name: /ambient label/i })).not.toBeInTheDocument();
    expect(screen.queryByTestId("ambient-label-none")).not.toBeInTheDocument();
  });
});

describe("VehicleCard SER tickets button", () => {
  beforeEach(() => {
    vi.mocked(getVehicle).mockResolvedValue({
      vehicle_id: "1",
      brand: "generic",
      display_name: "My scooter",
      vin: null,
      license_plate: null,
      config: { location_token: "tok" },
      ambient_label: null,
      is_owner: true,
    });
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it("renders the button when the vehicle has at least one ticket", () => {
    const vehicle = makeVehicle({ has_ser_tickets: true });
    renderWithProviders(
      <VehicleCard
        vehicle={vehicle}
        onEdit={noop}
        onDeleted={noop}
        onViewHistory={noop}
        onViewSerTickets={noop}
      />,
    );

    expect(screen.getByRole("button", { name: /view ser tickets/i })).toBeInTheDocument();
  });

  it("renders the button for a vehicle with only manually created tickets (has_ser_tickets still true)", () => {
    const vehicle = makeVehicle({ has_ser_tickets: true, location: null });
    renderWithProviders(
      <VehicleCard
        vehicle={vehicle}
        onEdit={noop}
        onDeleted={noop}
        onViewHistory={noop}
        onViewSerTickets={noop}
      />,
    );

    expect(screen.getByRole("button", { name: /view ser tickets/i })).toBeInTheDocument();
  });

  it("does not render the button when the vehicle has no tickets", () => {
    const vehicle = makeVehicle({ has_ser_tickets: false });
    renderWithProviders(
      <VehicleCard
        vehicle={vehicle}
        onEdit={noop}
        onDeleted={noop}
        onViewHistory={noop}
        onViewSerTickets={noop}
      />,
    );

    expect(screen.queryByRole("button", { name: /view ser tickets/i })).not.toBeInTheDocument();
  });

  it("calls onViewSerTickets with the vehicle when clicked", async () => {
    const onViewSerTickets = vi.fn();
    const vehicle = makeVehicle({ has_ser_tickets: true });
    renderWithProviders(
      <VehicleCard
        vehicle={vehicle}
        onEdit={noop}
        onDeleted={noop}
        onViewHistory={noop}
        onViewSerTickets={onViewSerTickets}
      />,
    );

    await userEvent.click(screen.getByRole("button", { name: /view ser tickets/i }));

    expect(onViewSerTickets).toHaveBeenCalledWith(vehicle);
  });
});

describe("VehicleCard set-location action", () => {
  beforeEach(() => {
    vi.mocked(getVehicle).mockResolvedValue({
      vehicle_id: "1",
      brand: "generic",
      display_name: "My scooter",
      vin: null,
      license_plate: null,
      config: { location_token: "tok" },
      ambient_label: null,
      is_owner: true,
    });
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it("shows the 'Set location' button for a generic vehicle", () => {
    const vehicle = makeVehicle({ brand: "generic" });
    renderWithProviders(
      <VehicleCard
        vehicle={vehicle}
        onEdit={noop}
        onDeleted={noop}
        onViewHistory={noop}
        onViewSerTickets={noop}
      />,
    );

    expect(screen.getByRole("button", { name: "Set location" })).toBeInTheDocument();
  });

  it("does not show the 'Set location' button for a Toyota vehicle", () => {
    const vehicle = makeVehicle({ brand: "toyota" });
    renderWithProviders(
      <VehicleCard
        vehicle={vehicle}
        onEdit={noop}
        onDeleted={noop}
        onViewHistory={noop}
        onViewSerTickets={noop}
      />,
    );

    expect(screen.queryByRole("button", { name: "Set location" })).not.toBeInTheDocument();
  });

  it("opens the SetVehicleLocationModal when the button is clicked", async () => {
    const vehicle = makeVehicle({ brand: "generic" });
    const user = userEvent.setup();
    renderWithProviders(
      <VehicleCard
        vehicle={vehicle}
        onEdit={noop}
        onDeleted={noop}
        onViewHistory={noop}
        onViewSerTickets={noop}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Set location" }));

    expect(screen.getByRole("dialog", { name: "Set location" })).toBeInTheDocument();
  });

  it("closes the modal and updates the displayed location after a full set-location round trip", async () => {
    vi.mocked(pushVehicleLocation).mockResolvedValue(undefined);
    const vehicle = makeVehicle({ brand: "generic", location: null });
    const user = userEvent.setup();
    renderWithProviders(<VehicleCardWithLocationState vehicle={vehicle} />);

    await user.click(screen.getByRole("button", { name: "Set location" }));
    expect(screen.getByRole("dialog", { name: "Set location" })).toBeInTheDocument();

    await user.type(screen.getByLabelText("Latitude"), "40.1");
    await user.type(screen.getByLabelText("Longitude"), "-3.5");
    await user.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => {
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    });
    expect(pushVehicleLocation).toHaveBeenCalledWith(
      "1",
      expect.objectContaining({ lat: 40.1, lon: -3.5 }),
    );
    expect(screen.getByText("Location: 40.10000, -3.50000")).toBeInTheDocument();
  });
});

describe("VehicleCard owner-only actions", () => {
  beforeEach(() => {
    vi.mocked(getVehicle).mockResolvedValue({
      vehicle_id: "1",
      brand: "generic",
      display_name: "My scooter",
      vin: null,
      license_plate: null,
      config: { location_token: "tok" },
      ambient_label: null,
      is_owner: true,
    });
    vi.mocked(listVehicleShares).mockResolvedValue({ vehicle_id: "1", sharees: [] });
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it("renders Edit, Delete, Share and Set location for the owner", () => {
    const vehicle = makeVehicle({ is_owner: true, brand: "generic" });
    renderWithProviders(
      <VehicleCard
        vehicle={vehicle}
        onEdit={noop}
        onDeleted={noop}
        onViewHistory={noop}
        onViewSerTickets={noop}
      />,
    );

    expect(screen.getByRole("button", { name: "Edit" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Delete" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Share" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Set location" })).toBeInTheDocument();
  });

  it("hides owner-only buttons for a sharee", () => {
    const vehicle = makeVehicle({ is_owner: false, brand: "generic" });
    renderWithProviders(
      <VehicleCard
        vehicle={vehicle}
        onEdit={noop}
        onDeleted={noop}
        onViewHistory={noop}
        onViewSerTickets={noop}
      />,
    );

    expect(screen.queryByRole("button", { name: "Edit" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Delete" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Share" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Set location" })).not.toBeInTheDocument();
  });

  it("keeps View history visible for a sharee when a location exists", () => {
    const vehicle = makeVehicle({
      is_owner: false,
      location: { latitude: 40.4168, longitude: -3.7038, recorded_at: "2024-01-01T00:00:00Z" },
    });
    renderWithProviders(
      <VehicleCard
        vehicle={vehicle}
        onEdit={noop}
        onDeleted={noop}
        onViewHistory={noop}
        onViewSerTickets={noop}
      />,
    );

    expect(screen.getByRole("button", { name: "View history" })).toBeInTheDocument();
  });

  it("hides the generic push URL config for a sharee", async () => {
    vi.mocked(getVehicle).mockResolvedValue({
      vehicle_id: "1",
      brand: "generic",
      display_name: "My scooter",
      vin: null,
      license_plate: null,
      config: { redacted: true },
      ambient_label: null,
      is_owner: false,
    });

    const vehicle = makeVehicle({ is_owner: false, brand: "generic" });
    renderWithProviders(
      <VehicleCard
        vehicle={vehicle}
        onEdit={noop}
        onDeleted={noop}
        onViewHistory={noop}
        onViewSerTickets={noop}
      />,
    );

    await waitFor(() => expect(getVehicle).toHaveBeenCalled());
    expect(screen.queryByText(/Push URL:/)).not.toBeInTheDocument();
  });

  it("hides the Toyota config for a sharee", async () => {
    vi.mocked(getVehicle).mockResolvedValue({
      vehicle_id: "2",
      brand: "toyota",
      display_name: "My car",
      vin: "VIN123",
      license_plate: null,
      config: { redacted: true },
      ambient_label: null,
      is_owner: false,
    });

    const vehicle = makeVehicle({ vehicle_id: "2", is_owner: false, brand: "toyota", vin: "VIN123" });
    renderWithProviders(
      <VehicleCard
        vehicle={vehicle}
        onEdit={noop}
        onDeleted={noop}
        onViewHistory={noop}
        onViewSerTickets={noop}
      />,
    );

    await waitFor(() => expect(getVehicle).toHaveBeenCalled());
    expect(screen.queryByText(/Username:/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Locale:/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Password:/)).not.toBeInTheDocument();
  });

  it("opens the ShareVehicleModal when Share is clicked", async () => {
    const vehicle = makeVehicle({ is_owner: true });
    const user = userEvent.setup();
    renderWithProviders(
      <VehicleCard
        vehicle={vehicle}
        onEdit={noop}
        onDeleted={noop}
        onViewHistory={noop}
        onViewSerTickets={noop}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Share" }));

    expect(screen.getByRole("dialog", { name: "Share Vehicle" })).toBeInTheDocument();
  });
});
