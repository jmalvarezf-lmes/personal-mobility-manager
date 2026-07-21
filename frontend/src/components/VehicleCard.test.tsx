import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { getVehicle } from "../api/vehicles";
import type { VehicleListItem } from "../types/vehicle";
import { renderWithProviders, screen } from "../test/render";
import VehicleCard from "./VehicleCard";

vi.mock("../api/vehicles");

function makeVehicle(overrides: Partial<VehicleListItem> = {}): VehicleListItem {
  return {
    vehicle_id: "1",
    brand: "generic",
    display_name: "My scooter",
    vin: null,
    license_plate: null,
    location: null,
    ambient_label: null,
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
      <VehicleCard vehicle={vehicle} onEdit={noop} onDeleted={noop} onViewHistory={noop} />,
    );

    const icon = screen.getByRole("img", { name: "Ambient label B" });
    expect(icon).toHaveAttribute("src", "/api/ambient-labels/B/icon");
  });

  it("renders the 'no label' indicator for a vehicle in category A", () => {
    const vehicle = makeVehicle({ ambient_label: "A" });
    renderWithProviders(
      <VehicleCard vehicle={vehicle} onEdit={noop} onDeleted={noop} onViewHistory={noop} />,
    );

    expect(screen.getByTestId("ambient-label-none")).toHaveTextContent("No label");
  });

  it("renders no ambient-label element for a vehicle with a null ambient label", () => {
    const vehicle = makeVehicle({ ambient_label: null });
    renderWithProviders(
      <VehicleCard vehicle={vehicle} onEdit={noop} onDeleted={noop} onViewHistory={noop} />,
    );

    expect(screen.queryByRole("img", { name: /ambient label/i })).not.toBeInTheDocument();
    expect(screen.queryByTestId("ambient-label-none")).not.toBeInTheDocument();
  });
});
