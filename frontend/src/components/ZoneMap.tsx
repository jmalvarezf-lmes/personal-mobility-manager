import "leaflet/dist/leaflet.css";
import type { Feature, Geometry } from "geojson";
import type { PathOptions } from "leaflet";
import { GeoJSON, MapContainer, TileLayer, Tooltip } from "react-leaflet";
import type { Zone } from "../types/zone";

const OSM_FALLBACK = "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png";
const MADRID_CENTER: [number, number] = [40.4168, -3.7038];

interface ZoneMapProps {
  zones: Zone[];
  tileUrl: string | null;
}

export default function ZoneMap({ zones, tileUrl }: ZoneMapProps) {
  return (
    <MapContainer
      center={MADRID_CENTER}
      zoom={13}
      className="h-full w-full"
    >
      <TileLayer
        url={tileUrl ?? OSM_FALLBACK}
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
      />
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
