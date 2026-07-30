import { describe, expect, it, vi } from "vitest";

import { renderWithProviders, screen } from "../test/render";
import type { Frontier, Zone } from "../types/zone";
import ZoneMap from "./ZoneMap";

vi.mock("react-leaflet", () => ({
  MapContainer: (props: { children?: React.ReactNode }) => (
    <div data-testid="map-container">{props.children}</div>
  ),
  TileLayer: (props: { url: string }) => <div data-testid="tile-layer" data-url={props.url} />,
  GeoJSON: (props: { children?: React.ReactNode; style?: { color?: string; interactive?: boolean } }) => (
    <div data-testid="geojson" data-color={props.style?.color}>
      {props.children}
    </div>
  ),
  Tooltip: (props: { children?: React.ReactNode }) => <div data-testid="tooltip">{props.children}</div>,
}));

const geometry = { type: "Polygon" as const, coordinates: [] };

const frontiers: Frontier[] = [{ zone_number: "1", neighbourhood: "Sol", geometry }];

const zones: Zone[] = [
  { zone_number: "1", zone_type: "Verde", colour: "#00ff00", district: "Centro", spot_count: 10, geometry },
  { zone_number: "1", zone_type: "Azul", colour: "#0000ff", district: "Centro", spot_count: 5, geometry },
  { zone_number: "1", zone_type: "Naranja", colour: "#ff8800", district: "Centro", spot_count: 0, geometry },
];

describe("ZoneMap", () => {
  it("renders the map container and tile layer with the given tile URL", () => {
    renderWithProviders(<ZoneMap zones={[]} frontiers={[]} tileUrl="https://tiles.example/{z}/{x}/{y}.png" />);

    expect(screen.getByTestId("map-container")).toBeInTheDocument();
    expect(screen.getByTestId("tile-layer")).toHaveAttribute(
      "data-url",
      "https://tiles.example/{z}/{x}/{y}.png",
    );
  });

  it("falls back to the OSM tile URL when tileUrl is null", () => {
    renderWithProviders(<ZoneMap zones={[]} frontiers={[]} tileUrl={null} />);

    expect(screen.getByTestId("tile-layer")).toHaveAttribute(
      "data-url",
      "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
    );
  });

  it("renders one frontier polygon with a tooltip showing the zone number and neighbourhood", () => {
    renderWithProviders(<ZoneMap zones={[]} frontiers={frontiers} tileUrl={null} />);

    const tooltip = screen.getByTestId("tooltip");
    expect(tooltip).toHaveTextContent("1");
    expect(tooltip).toHaveTextContent("Sol");
  });

  it("groups spot counts by zone_type in the frontier tooltip and excludes zero-count entries", () => {
    renderWithProviders(<ZoneMap zones={zones} frontiers={frontiers} tileUrl={null} />);

    const tooltip = screen.getByTestId("tooltip");
    expect(tooltip).toHaveTextContent("Verde: 10 plazas");
    expect(tooltip).toHaveTextContent("Azul: 5 plazas");
    expect(tooltip).not.toHaveTextContent("Naranja");
  });

  it("renders one non-interactive colour-fill polygon per zone", () => {
    renderWithProviders(<ZoneMap zones={zones} frontiers={[]} tileUrl={null} />);

    const geojsons = screen.getAllByTestId("geojson");
    expect(geojsons).toHaveLength(zones.length);
    expect(geojsons[0]).toHaveAttribute("data-color", zones[0].colour);
  });

  it("renders both frontier and zone polygons together", () => {
    renderWithProviders(<ZoneMap zones={zones} frontiers={frontiers} tileUrl={null} />);

    expect(screen.getAllByTestId("geojson")).toHaveLength(zones.length + frontiers.length);
    expect(screen.getAllByTestId("tooltip")).toHaveLength(frontiers.length);
  });
});
