import { describe, expect, it, vi } from "vitest";

import { renderWithProviders, screen } from "../test/render";
import type { VehicleListItem } from "../types/vehicle";
import VehicleMap from "./VehicleMap";

const fitBoundsMock = vi.fn();

vi.mock("react-leaflet", () => ({
  MapContainer: (props: { children?: React.ReactNode }) => (
    <div data-testid="map-container">{props.children}</div>
  ),
  TileLayer: () => <div data-testid="tile-layer" />,
  Marker: (props: { children?: React.ReactNode; position: [number, number] }) => (
    <div data-testid="marker" data-position={JSON.stringify(props.position)}>
      {props.children}
    </div>
  ),
  Popup: (props: { children?: React.ReactNode }) => <div data-testid="popup">{props.children}</div>,
  useMap: () => ({ fitBounds: fitBoundsMock }),
}));

function makeVehicle(overrides: Partial<VehicleListItem> = {}): VehicleListItem {
  return {
    vehicle_id: "veh-1",
    brand: "generic",
    display_name: "My Car",
    vin: null,
    license_plate: null,
    location: { latitude: 40.41, longitude: -3.7, recorded_at: "2024-01-01T00:00:00Z" },
    ambient_label: null,
    has_ser_tickets: false,
    ...overrides,
  };
}

describe("VehicleMap", () => {
  it("renders the map container and tile layer", () => {
    renderWithProviders(<VehicleMap vehicles={[]} />);

    expect(screen.getByTestId("map-container")).toBeInTheDocument();
    expect(screen.getByTestId("tile-layer")).toBeInTheDocument();
  });

  it("renders a marker with a popup for each vehicle that has a location", () => {
    const vehicles = [makeVehicle({ vehicle_id: "veh-1", display_name: "Car One" })];
    renderWithProviders(<VehicleMap vehicles={vehicles} />);

    const marker = screen.getByTestId("marker");
    expect(marker).toHaveAttribute("data-position", JSON.stringify([40.41, -3.7]));
    expect(screen.getByTestId("popup")).toHaveTextContent("Car One");
  });

  it("skips vehicles without a location", () => {
    const vehicles = [
      makeVehicle({ vehicle_id: "veh-1", location: null }),
      makeVehicle({ vehicle_id: "veh-2", display_name: "Car Two" }),
    ];
    renderWithProviders(<VehicleMap vehicles={vehicles} />);

    expect(screen.getAllByTestId("marker")).toHaveLength(1);
    expect(screen.getByTestId("popup")).toHaveTextContent("Car Two");
  });

  it("calls fitBounds with the positions of located vehicles", () => {
    const vehicles = [
      makeVehicle({ vehicle_id: "veh-1", location: { latitude: 1, longitude: 2, recorded_at: "x" } }),
      makeVehicle({ vehicle_id: "veh-2", location: { latitude: 3, longitude: 4, recorded_at: "x" } }),
    ];
    renderWithProviders(<VehicleMap vehicles={vehicles} />);

    expect(fitBoundsMock).toHaveBeenCalled();
  });

  it("renders no markers and does not call fitBounds when there are no vehicles", () => {
    fitBoundsMock.mockClear();
    renderWithProviders(<VehicleMap vehicles={[]} />);

    expect(screen.queryByTestId("marker")).not.toBeInTheDocument();
    expect(fitBoundsMock).not.toHaveBeenCalled();
  });
});
