import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { getPreferences } from "../api/preferences";
import { getSerTicketHistory } from "../api/vehicles";
import type { SerTicket, VehicleListItem } from "../types/vehicle";
import { renderWithProviders, screen, waitFor } from "../test/render";
import VehicleSerTicketHistoryModal from "./VehicleSerTicketHistoryModal";

vi.mock("../api/vehicles");
vi.mock("../api/preferences");

vi.mock("leaflet", () => ({
  default: {
    divIcon: vi.fn(() => ({})),
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
  Marker: ({
    children,
    position,
  }: {
    children: React.ReactNode;
    position: [number, number];
  }) => (
    <div data-testid="marker" data-position={JSON.stringify(position)}>
      {children}
    </div>
  ),
  Popup: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="popup">{children}</div>
  ),
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
    has_ser_tickets: true,
    ...overrides,
  };
}

function makeTicket(overrides: Partial<SerTicket> = {}): SerTicket {
  return {
    id: "ticket-1",
    latitude: 40.4168,
    longitude: -3.7038,
    start_date: "2026-07-01T10:00:00Z",
    end_date: "2026-07-01T11:00:00Z",
    city_code: "madrid",
    city_name: "Madrid",
    zone_number: "163",
    auto_created: true,
    ...overrides,
  };
}

const noop = () => undefined;

describe("VehicleSerTicketHistoryModal", () => {
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

  it("loads and renders the first page of tickets", async () => {
    vi.mocked(getSerTicketHistory).mockResolvedValue({
      items: [makeTicket()],
      has_more: false,
    });

    renderWithProviders(
      <VehicleSerTicketHistoryModal vehicle={makeVehicle()} onClose={noop} />,
    );

    await waitFor(() => {
      expect(getSerTicketHistory).toHaveBeenCalledWith("veh-1", { limit: 5, offset: 0 });
    });
    expect(await screen.findByText(/Madrid/)).toBeInTheDocument();
  });

  it("shows the load-more control when has_more is true and hides it once exhausted", async () => {
    vi.mocked(getSerTicketHistory)
      .mockResolvedValueOnce({ items: [makeTicket({ id: "t1" })], has_more: true })
      .mockResolvedValueOnce({ items: [makeTicket({ id: "t2" })], has_more: false });

    renderWithProviders(
      <VehicleSerTicketHistoryModal vehicle={makeVehicle()} onClose={noop} />,
    );

    const loadMore = await screen.findByRole("button", { name: /load more/i });
    loadMore.click();

    await waitFor(() => {
      expect(getSerTicketHistory).toHaveBeenCalledWith("veh-1", { limit: 5, offset: 1 });
    });
    await waitFor(() => {
      expect(screen.queryByRole("button", { name: /load more/i })).not.toBeInTheDocument();
    });
  });

  it("renders a single marker with no polyline for a ticket with coordinates", async () => {
    vi.mocked(getSerTicketHistory).mockResolvedValue({
      items: [makeTicket()],
      has_more: false,
    });

    renderWithProviders(
      <VehicleSerTicketHistoryModal vehicle={makeVehicle()} onClose={noop} />,
    );

    await screen.findByTestId("map-container");
    expect(screen.getAllByTestId("marker")).toHaveLength(1);
    expect(screen.queryByTestId("polyline")).not.toBeInTheDocument();
  });

  it("omits the map for a ticket with null coordinates", async () => {
    vi.mocked(getSerTicketHistory).mockResolvedValue({
      items: [makeTicket({ latitude: null, longitude: null })],
      has_more: false,
    });

    renderWithProviders(
      <VehicleSerTicketHistoryModal vehicle={makeVehicle()} onClose={noop} />,
    );

    await screen.findByText(/Madrid/);
    expect(screen.queryByTestId("map-container")).not.toBeInTheDocument();
  });

  it("falls back from city_name to city_code, then to a placeholder", async () => {
    vi.mocked(getSerTicketHistory).mockResolvedValue({
      items: [
        makeTicket({ id: "t1", city_name: null, city_code: "MAD" }),
        makeTicket({ id: "t2", city_name: null, city_code: null }),
      ],
      has_more: false,
    });

    renderWithProviders(
      <VehicleSerTicketHistoryModal vehicle={makeVehicle()} onClose={noop} />,
    );

    expect(await screen.findByText(/MAD/)).toBeInTheDocument();
    expect(screen.getByText(/Unknown city/)).toBeInTheDocument();
  });

  it("shows the automatic provenance label for auto_created=true, badged green", async () => {
    vi.mocked(getSerTicketHistory).mockResolvedValue({
      items: [makeTicket({ auto_created: true })],
      has_more: false,
    });

    renderWithProviders(
      <VehicleSerTicketHistoryModal vehicle={makeVehicle()} onClose={noop} />,
    );

    const badge = await screen.findByText("Automatic");
    expect(badge).toBeInTheDocument();
    expect(badge.className).toContain("bg-green-100");
    expect(badge.className).toContain("text-green-700");
  });

  it("shows the manual provenance label for auto_created=false, badged gray", async () => {
    vi.mocked(getSerTicketHistory).mockResolvedValue({
      items: [makeTicket({ auto_created: false })],
      has_more: false,
    });

    renderWithProviders(
      <VehicleSerTicketHistoryModal vehicle={makeVehicle()} onClose={noop} />,
    );

    const badge = await screen.findByText("Manual");
    expect(badge).toBeInTheDocument();
    expect(badge.className).toContain("bg-gray-100");
    expect(badge.className).toContain("text-gray-700");
  });

  it("shows the unknown provenance label for auto_created=null, badged amber", async () => {
    vi.mocked(getSerTicketHistory).mockResolvedValue({
      items: [makeTicket({ auto_created: null })],
      has_more: false,
    });

    renderWithProviders(
      <VehicleSerTicketHistoryModal vehicle={makeVehicle()} onClose={noop} />,
    );

    const badge = await screen.findByText("Unknown");
    expect(badge).toBeInTheDocument();
    expect(badge.className).toContain("bg-amber-100");
    expect(badge.className).toContain("text-amber-700");
  });

  it("shows an empty state when the vehicle has no tickets", async () => {
    vi.mocked(getSerTicketHistory).mockResolvedValue({ items: [], has_more: false });

    renderWithProviders(
      <VehicleSerTicketHistoryModal vehicle={makeVehicle()} onClose={noop} />,
    );

    expect(await screen.findByText(/no ser tickets/i)).toBeInTheDocument();
  });

  it("formats dates using the resolved display timezone", async () => {
    vi.mocked(getSerTicketHistory).mockResolvedValue({
      items: [makeTicket({ start_date: "2026-07-01T10:00:00Z" })],
      has_more: false,
    });

    renderWithProviders(
      <VehicleSerTicketHistoryModal vehicle={makeVehicle()} onClose={noop} />,
    );

    await waitFor(() => {
      expect(screen.getByText(/Start date/i).parentElement?.textContent).toMatch(/2026-07-01/);
    });
  });
});
