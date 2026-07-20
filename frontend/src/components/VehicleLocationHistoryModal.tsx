import "leaflet/dist/leaflet.css";
import L from "leaflet";
import { useEffect, useState } from "react";
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

const OSM_FALLBACK = "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png";
const PAGE_SIZE = 5;

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
  // newest-first, matching API response order — see the reversal comment
  // below at the point the polyline/map order is derived from this array.
  const [locations, setLocations] = useState<VehicleLocation[]>([]);
  const [offset, setOffset] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    getVehicleLocationHistory(vehicle.vehicle_id, { limit: PAGE_SIZE, offset: 0 })
      .then((page) => {
        if (cancelled) return;
        setLocations(page.items);
        setHasMore(page.has_more);
        setOffset(page.items.length);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setError(
          err instanceof Error ? err.message : t("modal.locationHistory.title"),
        );
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
    // Reload from scratch whenever a fresh modal instance mounts for this
    // vehicle — closing and reopening discards any previously loaded pages
    // (see vehicle-location-history-ui spec: "Reopening starts fresh").
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [vehicle.vehicle_id]);

  async function handleLoadMore() {
    setLoadingMore(true);
    setError(null);
    try {
      const page = await getVehicleLocationHistory(vehicle.vehicle_id, {
        limit: PAGE_SIZE,
        offset,
      });
      setLocations((prev) => [...prev, ...page.items]);
      setHasMore(page.has_more);
      setOffset((prev) => prev + page.items.length);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : t("modal.locationHistory.loadMore"),
      );
    } finally {
      setLoadingMore(false);
    }
  }

  // The API returns locations newest-first (same order used by the list
  // below), but the polyline must be drawn oldest -> newest so the route
  // reads chronologically on the map. This reversed copy is ONLY for the
  // map/polyline — the list below intentionally keeps the original
  // newest-first order. Easy to get backwards, hence this comment.
  const chronological = [...locations].reverse();
  const positions: [number, number][] = chronological.map((loc) => [
    loc.latitude,
    loc.longitude,
  ]);

  // One directional arrow per segment between chronologically consecutive
  // points, placed at the segment midpoint and rotated to point from the
  // older point toward the newer one. Empty when there's only one point
  // (no segments), matching the polyline's own single-point behaviour.
  const segmentArrows = positions.slice(1).map((p2, i) => {
    const p1 = positions[i];
    return {
      key: `${p1[0]},${p1[1]}-${p2[0]},${p2[1]}`,
      midpoint: [(p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2] as [number, number],
      bearing: bearingDegrees(p1, p2),
    };
  });

  const isEmpty = !loading && locations.length === 0 && !error;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={t("modal.locationHistory.title", { name: vehicle.display_name })}
      className="fixed inset-0 z-[1001] flex items-center justify-center bg-black/40"
    >
      <div className="flex max-h-[85vh] w-full max-w-lg flex-col rounded bg-white p-6 shadow-lg">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold">
            {t("modal.locationHistory.title", { name: vehicle.display_name })}
          </h2>
          <button
            type="button"
            onClick={onClose}
            className="rounded bg-gray-100 px-3 py-1 text-sm hover:bg-gray-200"
          >
            {t("common.cancel")}
          </button>
        </div>

        {error && (
          <p role="alert" className="mb-3 text-sm text-red-600">
            {error}
          </p>
        )}

        {loading && (
          <p className="text-sm text-gray-500">{t("modal.locationHistory.loading")}</p>
        )}

        {isEmpty && (
          <p className="text-sm italic text-gray-400">
            {t("modal.locationHistory.empty")}
          </p>
        )}

        {!loading && locations.length > 0 && (
          <div className="flex flex-1 flex-col gap-4 overflow-hidden">
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
                      <Popup>{loc.recorded_at}</Popup>
                    </Marker>
                  ) : (
                    <CircleMarker
                      key={`${loc.recorded_at}-${index}`}
                      center={[loc.latitude, loc.longitude]}
                      radius={6}
                      pathOptions={{ color: "#2563eb", fillColor: "#93c5fd", fillOpacity: 1 }}
                    >
                      <Popup>{loc.recorded_at}</Popup>
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
                  <span>{loc.recorded_at}</span>
                  <span>
                    {loc.latitude.toFixed(6)}, {loc.longitude.toFixed(6)}
                  </span>
                </div>
              ))}
            </div>

            {hasMore && (
              <button
                type="button"
                onClick={() => void handleLoadMore()}
                disabled={loadingMore}
                className="rounded bg-gray-100 px-4 py-2 text-sm hover:bg-gray-200 disabled:opacity-50"
              >
                {loadingMore
                  ? t("modal.locationHistory.loadingMore")
                  : t("modal.locationHistory.loadMore")}
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
