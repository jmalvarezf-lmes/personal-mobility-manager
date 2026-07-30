import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { getVehicle, pushVehicleLocation } from "../api/vehicles";
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
