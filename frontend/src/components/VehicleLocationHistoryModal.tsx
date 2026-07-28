import "leaflet/dist/leaflet.css";
import L from "leaflet";
import { useEffect } from "react";
import { useTranslation } from "react-i18next";
import {
  CircleMarker,
  MapContainer,
  Marker,
  Polyline,
  Popup,
  TileLayer,
  useMap,
} from "react-leaflet";
import { getVehicleLocationHistory } from "../api/vehicles";
import type { VehicleListItem, VehicleLocation } from "../types/vehicle";
import { formatInTimezone } from "../utils/timezone";
import HistoryModal, { OSM_FALLBACK } from "./HistoryModal";

// Same car-style DivIcon used for "current location" on the shared
// VehicleMap, reused here for visual continuity on the newest pin.
const newestIcon = L.divIcon({
  html: '<div style="font-size:24px;line-height:1">🚗</div>',
  className: "",
  iconSize: [32, 32],
  iconAnchor: [16, 16],
});

// Standard compass bearing (0-360deg, 0 = north) from p1 to p2.
function bearingDegrees(
  p1: [number, number],
  p2: [number, number],
): number {
  const lat1 = (p1[0] * Math.PI) / 180;
  const lat2 = (p2[0] * Math.PI) / 180;
  const deltaLon = ((p2[1] - p1[1]) * Math.PI) / 180;

  const y = Math.sin(deltaLon) * Math.cos(lat2);
  const x =
    Math.cos(lat1) * Math.sin(lat2) -
    Math.sin(lat1) * Math.cos(lat2) * Math.cos(deltaLon);
  const bearing = (Math.atan2(y, x) * 180) / Math.PI;
  return (bearing + 360) % 360;
}

function arrowIcon(bearing: number): L.DivIcon {
  return L.divIcon({
    html: `<div style="transform: rotate(${bearing}deg); font-size:14px; line-height:1; color:#2563eb;">▲</div>`,
    className: "",
    iconSize: [14, 14],
    iconAnchor: [7, 7],
  });
}

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

interface VehicleLocationHistoryModalProps {
  vehicle: VehicleListItem;
  onClose: () => void;
}

export default function VehicleLocationHistoryModal({
  vehicle,
  onClose,
}: VehicleLocationHistoryModalProps) {
  const { t } = useTranslation();

  return (
    <HistoryModal<VehicleLocation>
      title={t("modal.locationHistory.title", { name: vehicle.display_name })}
      onClose={onClose}
      vehicleId={vehicle.vehicle_id}
      fetchPage={getVehicleLocationHistory}
      contentClassName="flex flex-1 flex-col gap-4 overflow-hidden"
      messages={{
        loading: t("modal.locationHistory.loading"),
        loadingMore: t("modal.locationHistory.loadingMore"),
        loadMore: t("modal.locationHistory.loadMore"),
        empty: t("modal.locationHistory.empty"),
        error: t("modal.locationHistory.error"),
      }}
    >
      {({ items: locations, displayTimezone }) => {
        // The API returns locations newest-first (same order used by the
        // list below), but the polyline must be drawn oldest -> newest so
        // the route reads chronologically on the map. This reversed copy is
        // ONLY for the map/polyline — the list below intentionally keeps
        // the original newest-first order. Easy to get backwards, hence
        // this comment.
        const chronological = [...locations].reverse();
        const positions: [number, number][] = chronological.map((loc) => [
          loc.latitude,
          loc.longitude,
        ]);

        // One directional arrow per segment between chronologically
        // consecutive points, placed at the segment midpoint and rotated to
        // point from the older point toward the newer one. Empty when
        // there's only one point (no segments), matching the polyline's own
        // single-point behaviour.
        const segmentArrows = positions.slice(1).map((p2, i) => {
          const p1 = positions[i];
          return {
            key: `${p1[0]},${p1[1]}-${p2[0]},${p2[1]}`,
            midpoint: [(p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2] as [number, number],
            bearing: bearingDegrees(p1, p2),
          };
        });

        return (
          <>
            <div className="h-56 shrink-0 overflow-hidden rounded border border-gray-200">
              <MapContainer center={positions[0]} zoom={13} className="h-full w-full">
                <TileLayer
                  url={OSM_FALLBACK}
                  attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
                />
                <FitBounds positions={positions} />
                <Polyline positions={positions} pathOptions={{ color: "#2563eb" }} />
                {segmentArrows.map((arrow) => (
                  <Marker
                    key={arrow.key}
                    position={arrow.midpoint}
                    icon={arrowIcon(arrow.bearing)}
                    interactive={false}
                  />
                ))}
                {locations.map((loc, index) =>
                  index === 0 ? (
                    <Marker
                      key={`${loc.recorded_at}-${index}`}
                      position={[loc.latitude, loc.longitude]}
                      icon={newestIcon}
                    >
                      <Popup>{formatInTimezone(loc.recorded_at, displayTimezone)}</Popup>
                    </Marker>
                  ) : (
                    <CircleMarker
                      key={`${loc.recorded_at}-${index}`}
                      center={[loc.latitude, loc.longitude]}
                      radius={6}
                      pathOptions={{ color: "#2563eb", fillColor: "#93c5fd", fillOpacity: 1 }}
                    >
                      <Popup>{formatInTimezone(loc.recorded_at, displayTimezone)}</Popup>
                    </CircleMarker>
                  ),
                )}
              </MapContainer>
            </div>

            <div className="flex-1 space-y-1 overflow-y-auto">
              {locations.map((loc, index) => (
                <div
                  key={`${loc.recorded_at}-${index}`}
                  className="flex items-center justify-between border-b border-gray-100 py-1 text-sm text-gray-600"
                >
                  <span>{formatInTimezone(loc.recorded_at, displayTimezone)}</span>
                  <span>
                    {loc.latitude.toFixed(6)}, {loc.longitude.toFixed(6)}
                  </span>
                </div>
              ))}
            </div>
          </>
        );
      }}
    </HistoryModal>
  );
}
