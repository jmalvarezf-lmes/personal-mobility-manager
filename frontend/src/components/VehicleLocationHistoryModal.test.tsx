import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { getPreferences } from "../api/preferences";
import { getVehicleLocationHistory } from "../api/vehicles";
import type { VehicleListItem, VehicleLocation } from "../types/vehicle";
import { renderWithProviders, screen, waitFor } from "../test/render";
import VehicleLocationHistoryModal from "./VehicleLocationHistoryModal";

vi.mock("../api/vehicles");
vi.mock("../api/preferences");

vi.mock("leaflet", () => ({
  default: {
    divIcon: vi.fn(() => ({})),
    latLngBounds: vi.fn(() => ({})),
  },
}));

vi.mock("react-leaflet", () => ({
  MapContainer: ({
    children,
    center,
  }: {
    children: React.ReactNode;
    center: [number, number];
  }) => (
    <div data-testid="map-container" data-center={JSON.stringify(center)}>
      {children}
    </div>
  ),
  TileLayer: () => <div data-testid="tile-layer" />,
  Polyline: ({ positions }: { positions: [number, number][] }) => (
    <div data-testid="polyline" data-positions={JSON.stringify(positions)} />
  ),
  Marker: ({
    children,
    position,
  }: {
    children?: React.ReactNode;
    position: [number, number];
  }) => (
    <div data-testid="marker" data-position={JSON.stringify(position)}>
      {children}
    </div>
  ),
  CircleMarker: ({
    children,
    center,
  }: {
    children?: React.ReactNode;
    center: [number, number];
  }) => (
    <div data-testid="circle-marker" data-center={JSON.stringify(center)}>
      {children}
    </div>
  ),
  Popup: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="popup">{children}</div>
  ),
  useMap: () => ({ fitBounds: vi.fn() }),
}));

function makeVehicle(overrides: Partial<VehicleListItem> = {}): VehicleListItem {
  return {
    vehicle_id: "veh-1",
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

function makeLocation(overrides: Partial<VehicleLocation> = {}): VehicleLocation {
  return {
    latitude: 40.4168,
    longitude: -3.7038,
    recorded_at: "2026-07-01T10:00:00Z",
    ...overrides,
  };
}

const noop = () => undefined;

describe("VehicleLocationHistoryModal", () => {
  beforeEach(() => {
    vi.mocked(getPreferences).mockResolvedValue({
      default_ticket_duration_minutes: 60,
      auto_create_ticket: false,
      preferred_notification_channel: null,
      notification_language: null,
      timezone: "UTC",
    });
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it("loads and renders the first page of locations", async () => {
    vi.mocked(getVehicleLocationHistory).mockResolvedValue({
      items: [makeLocation()],
      has_more: false,
    });

    renderWithProviders(
      <VehicleLocationHistoryModal vehicle={makeVehicle()} onClose={noop} />,
    );

    await waitFor(() => {
      expect(getVehicleLocationHistory).toHaveBeenCalledWith("veh-1", { limit: 5, offset: 0 });
    });
    expect(await screen.findByRole("dialog")).toBeInTheDocument();
    expect(await screen.findByTestId("polyline")).toBeInTheDocument();
  });

  it("shows the load-more control when has_more is true and hides it once exhausted", async () => {
    vi.mocked(getVehicleLocationHistory)
      .mockResolvedValueOnce({
        items: [makeLocation({ recorded_at: "2026-07-01T10:00:00Z" })],
        has_more: true,
      })
      .mockResolvedValueOnce({
        items: [makeLocation({ recorded_at: "2026-07-01T09:00:00Z" })],
        has_more: false,
      });

    renderWithProviders(
      <VehicleLocationHistoryModal vehicle={makeVehicle()} onClose={noop} />,
    );

    const loadMore = await screen.findByRole("button", { name: /load more/i });
    loadMore.click();

    await waitFor(() => {
      expect(getVehicleLocationHistory).toHaveBeenCalledWith("veh-1", { limit: 5, offset: 1 });
    });
    await waitFor(() => {
      expect(screen.queryByRole("button", { name: /load more/i })).not.toBeInTheDocument();
    });
  });

  it("renders the newest location with a distinct marker from older CircleMarker points", async () => {
    vi.mocked(getVehicleLocationHistory).mockResolvedValue({
      items: [
        makeLocation({ recorded_at: "2026-07-01T11:00:00Z" }),
        makeLocation({ recorded_at: "2026-07-01T10:00:00Z" }),
      ],
      has_more: false,
    });

    renderWithProviders(
      <VehicleLocationHistoryModal vehicle={makeVehicle()} onClose={noop} />,
    );

    await screen.findByTestId("map-container");
    expect(screen.getAllByTestId("marker").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByTestId("circle-marker")).toHaveLength(1);
  });

  it("shows an empty state when the vehicle has no location history", async () => {
    vi.mocked(getVehicleLocationHistory).mockResolvedValue({ items: [], has_more: false });

    renderWithProviders(
      <VehicleLocationHistoryModal vehicle={makeVehicle()} onClose={noop} />,
    );

    expect(await screen.findByText(/no location history/i)).toBeInTheDocument();
  });

  it("formats dates using the resolved display timezone", async () => {
    vi.mocked(getVehicleLocationHistory).mockResolvedValue({
      items: [makeLocation({ recorded_at: "2026-07-01T10:00:00Z" })],
      has_more: false,
    });

    renderWithProviders(
      <VehicleLocationHistoryModal vehicle={makeVehicle()} onClose={noop} />,
    );

    await waitFor(() => {
      expect(screen.getByTestId("popup").textContent).toMatch(/2026-07-01/);
    });
  });
});
