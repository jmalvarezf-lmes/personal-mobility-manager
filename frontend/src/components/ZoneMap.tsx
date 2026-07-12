import "leaflet/dist/leaflet.css";
import type { Feature, Geometry } from "geojson";
import type { PathOptions } from "leaflet";
import { useMemo } from "react";
import { GeoJSON, MapContainer, TileLayer, Tooltip } from "react-leaflet";
import type { Frontier, Zone } from "../types/zone";

const OSM_FALLBACK = "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png";
const MADRID_CENTER: [number, number] = [40.4168, -3.7038];

// Fixed neutral style for every frontier polygon, regardless of which SER
// colours its zone_number contains — see design.md D8. A zone_number's
// frontier can span multiple colours, so no single zone colour is correct.
// Fill references the diagonal-hatch pattern defined in FRONTIER_HATCH_ID
// below, rather than a flat translucent fill, so it stays visible against
// every basemap tile colour instead of blending in.
const FRONTIER_HATCH_ID = "zone-frontier-hatch";
const FRONTIER_STYLE: PathOptions = {
  className: "zone-frontier",
  color: "#4B5563",
  fillColor: `url(#${FRONTIER_HATCH_ID})`,
  fillOpacity: 0.6,
  weight: 2.5,
};

interface ZoneMapProps {
  zones: Zone[];
  frontiers: Frontier[];
  tileUrl: string | null;
}

interface SpotBreakdown {
  zoneType: string;
  colour: string;
  spotCount: number;
}

// Groups each zone_number's street/band polygons by zone_type (colour) and
// sums their spot_count, so the frontier tooltip can show a single
// per-colour breakdown instead of the street layer needing its own tooltip.
function groupSpotsByZoneNumber(zones: Zone[]): Map<string, SpotBreakdown[]> {
  const byZoneNumber = new Map<string, Map<string, SpotBreakdown>>();
  for (const zone of zones) {
    let byType = byZoneNumber.get(zone.zone_number);
    if (!byType) {
      byType = new Map();
      byZoneNumber.set(zone.zone_number, byType);
    }
    const existing = byType.get(zone.zone_type);
    if (existing) {
      existing.spotCount += zone.spot_count;
    } else {
      byType.set(zone.zone_type, {
        zoneType: zone.zone_type,
        colour: zone.colour,
        spotCount: zone.spot_count,
      });
    }
  }
  const result = new Map<string, SpotBreakdown[]>();
  for (const [zoneNumber, byType] of byZoneNumber) {
    result.set(
      zoneNumber,
      [...byType.values()].filter((breakdown) => breakdown.spotCount > 0),
    );
  }
  return result;
}

export default function ZoneMap({ zones, frontiers, tileUrl }: ZoneMapProps) {
  const spotBreakdownByZoneNumber = useMemo(() => groupSpotsByZoneNumber(zones), [zones]);
  return (
    <MapContainer
      center={MADRID_CENTER}
      zoom={13}
      className="h-full w-full"
    >
      <svg width="0" height="0" className="absolute">
        <defs>
          <pattern
            id={FRONTIER_HATCH_ID}
            patternUnits="userSpaceOnUse"
            width="6"
            height="6"
            patternTransform="rotate(45)"
          >
            <rect width="6" height="6" fill="transparent" />
            <line x1="0" y1="0" x2="0" y2="6" stroke="#6B7280" strokeWidth="2.5" />
          </pattern>
        </defs>
      </svg>
      <TileLayer
        url={tileUrl ?? OSM_FALLBACK}
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
      />
      {frontiers.map((frontier) => {
        const feature: Feature = {
          type: "Feature",
          properties: {},
          geometry: frontier.geometry as Geometry,
        };
        const spotBreakdown = spotBreakdownByZoneNumber.get(frontier.zone_number) ?? [];
        return (
          <GeoJSON
            key={`frontier-${frontier.zone_number}`}
            data={feature}
            style={FRONTIER_STYLE}
          >
            <Tooltip sticky>
              <span className="font-semibold">{frontier.zone_number}</span>
              <br />
              {frontier.neighbourhood}
              {spotBreakdown.map((breakdown) => (
                <div key={breakdown.zoneType} className="flex items-center gap-1">
                  <span
                    className="inline-block h-2 w-2 shrink-0 rounded-full"
                    style={{ backgroundColor: breakdown.colour }}
                  />
                  {breakdown.zoneType}: {breakdown.spotCount} plazas
                </div>
              ))}
            </Tooltip>
          </GeoJSON>
        );
      })}
      {zones.map((zone) => {
        const feature: Feature = {
          type: "Feature",
          properties: {},
          geometry: zone.geometry as Geometry,
        };
        // Non-interactive: purely a colour fill. Mouse events must pass
        // through to the frontier polygon beneath so hovering anywhere in
        // the neighbourhood — including over a street band — shows the
        // single frontier tooltip instead of a separate one here.
        const pathOptions: PathOptions = {
          color: zone.colour,
          fillColor: zone.colour,
          fillOpacity: 0.5,
          weight: 2,
          interactive: false,
        };
        return <GeoJSON key={`${zone.zone_number}-${zone.zone_type}`} data={feature} style={pathOptions} />;
      })}
    </MapContainer>
  );
}
