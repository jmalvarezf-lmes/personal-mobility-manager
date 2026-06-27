import "leaflet/dist/leaflet.css";
import L from "leaflet";
import { CircleMarker, MapContainer, TileLayer, Tooltip } from "react-leaflet";
import type { Zone } from "../types/zone";

const OSM_FALLBACK = "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png";
const MADRID_CENTER: [number, number] = [40.4168, -3.7038];
const canvas = L.canvas();

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
      {zones.map((zone, idx) => (
        <CircleMarker
          key={idx}
          center={[zone.lat, zone.lng]}
          radius={6}
          renderer={canvas}
          pathOptions={{
            color: zone.colour,
            fillColor: zone.colour,
            fillOpacity: 0.8,
            weight: 1,
          }}
        >
          <Tooltip>
            <span className="font-semibold">{zone.street_name}</span>
            <br />
            {zone.zone_type}
            {zone.spot_count > 0 && (
              <>
                <br />
                {zone.spot_count} plazas
              </>
            )}
          </Tooltip>
        </CircleMarker>
      ))}
    </MapContainer>
  );
}
