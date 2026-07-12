import "leaflet/dist/leaflet.css";
import type { Feature, Geometry } from "geojson";
import type { PathOptions } from "leaflet";
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

export default function ZoneMap({ zones, frontiers, tileUrl }: ZoneMapProps) {
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
        const pathOptions: PathOptions = {
          color: zone.colour,
          fillColor: zone.colour,
          fillOpacity: 0.5,
          weight: 2,
        };
        return (
          <GeoJSON
            key={`${zone.zone_number}-${zone.zone_type}`}
            data={feature}
            style={pathOptions}
          >
            <Tooltip sticky>
              <span className="font-semibold">{zone.zone_number}</span>
              <br />
              {zone.district}
              {zone.spot_count > 0 && (
                <>
                  <br />
                  {zone.spot_count} plazas
                </>
              )}
            </Tooltip>
          </GeoJSON>
        );
      })}
    </MapContainer>
  );
}
