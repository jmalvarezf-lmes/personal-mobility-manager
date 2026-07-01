import "leaflet/dist/leaflet.css";
import L from "leaflet";
import { useEffect } from "react";
import { MapContainer, Marker, Popup, TileLayer, useMap } from "react-leaflet";
import type { VehicleListItem } from "../types/vehicle";

const OSM_FALLBACK = "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png";
const MADRID_CENTER: [number, number] = [40.4168, -3.7038];

const carIcon = L.divIcon({
  html: '<div style="font-size:24px;line-height:1">🚗</div>',
  className: "",
  iconSize: [32, 32],
  iconAnchor: [16, 16],
});

interface FitBoundsProps {
  positions: [number, number][];
}

function FitBounds({ positions }: FitBoundsProps) {
  const map = useMap();
  useEffect(() => {
    if (positions.length > 0) {
      map.fitBounds(L.latLngBounds(positions), { padding: [40, 40] });
    }
  }, [map, positions]);
  return null;
}

interface VehicleMapProps {
  vehicles: VehicleListItem[];
}

export default function VehicleMap({ vehicles }: VehicleMapProps) {
  const positions: [number, number][] = vehicles
    .filter((v) => v.location != null)
    .map((v) => [v.location!.latitude, v.location!.longitude]);

  return (
    <MapContainer
      center={MADRID_CENTER}
      zoom={13}
      className="h-full w-full"
    >
      <TileLayer
        url={OSM_FALLBACK}
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
      />
      <FitBounds positions={positions} />
      {vehicles
        .filter((v) => v.location != null)
        .map((v) => (
          <Marker
            key={v.vehicle_id}
            position={[v.location!.latitude, v.location!.longitude]}
            icon={carIcon}
          >
            <Popup>{v.display_name}</Popup>
          </Marker>
        ))}
    </MapContainer>
  );
}
