import { useState } from "react";
import { useTranslation } from "react-i18next";
import { pushVehicleLocation } from "../api/vehicles";
import type { VehicleLocation } from "../types/vehicle";
import Button from "./ui/Button";
import Input from "./ui/Input";

interface SetVehicleLocationModalProps {
  vehicleId: string;
  onClose: () => void;
  onSaved: (location: VehicleLocation) => void;
}

/**
 * Modal for a generic vehicle's owner to submit a location update from
 * their own logged-in browser session — either via Browser Geolocation
 * autofill or manual lat/lng entry (design.md "Frontend: single modal,
 * geolocation as autofill (Shape A)"). Follows the AddVehicleModal /
 * EditVehicleModal overlay pattern.
 */
export default function SetVehicleLocationModal({
  vehicleId,
  onClose,
  onSaved,
}: SetVehicleLocationModalProps) {
  const { t } = useTranslation();
  const [latitude, setLatitude] = useState("");
  const [longitude, setLongitude] = useState("");
  const [geoError, setGeoError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [locating, setLocating] = useState(false);

  function handleUseCurrentLocation() {
    setGeoError(null);
    if (!navigator.geolocation) {
      setGeoError(t("modal.setLocation.geolocationError"));
      return;
    }
    setLocating(true);
    navigator.geolocation.getCurrentPosition(
      (position) => {
        setLatitude(String(position.coords.latitude));
        setLongitude(String(position.coords.longitude));
        setLocating(false);
      },
      () => {
        setGeoError(t("modal.setLocation.geolocationError"));
        setLocating(false);
      },
      { timeout: 10000 },
    );
  }

  function parsedCoordinates(): { lat: number; lon: number } | null {
    const lat = Number(latitude);
    const lon = Number(longitude);
    if (latitude === "" || longitude === "" || Number.isNaN(lat) || Number.isNaN(lon)) {
      return null;
    }
    if (lat < -90 || lat > 90 || lon < -180 || lon > 180) {
      return null;
    }
    return { lat, lon };
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    const coords = parsedCoordinates();
    if (!coords) {
      setError(t("modal.setLocation.validationError"));
      return;
    }
    setSubmitting(true);
    try {
      const recorded_at = new Date().toISOString();
      await pushVehicleLocation(vehicleId, {
        lat: coords.lat,
        lon: coords.lon,
        recorded_at,
      });
      onSaved({ latitude: coords.lat, longitude: coords.lon, recorded_at });
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("modal.setLocation.title"));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={t("modal.setLocation.title")}
      className="fixed inset-0 z-[1001] flex items-center justify-center bg-black/40"
    >
      <div className="w-full max-w-md rounded bg-white p-6 shadow-lg">
        <h2 className="mb-4 text-lg font-semibold">{t("modal.setLocation.title")}</h2>
        <form onSubmit={(e) => void handleSubmit(e)} className="space-y-3">
          <Button type="button" variant="secondary" onClick={handleUseCurrentLocation} disabled={locating}>
            {locating ? t("modal.setLocation.locating") : t("modal.setLocation.useCurrentLocation")}
          </Button>

          {geoError && (
            <p role="alert" className="text-sm text-red-600">
              {geoError}
            </p>
          )}

          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700" htmlFor="set-location-latitude">
              {t("modal.setLocation.latitude")}
            </label>
            <Input
              id="set-location-latitude"
              type="number"
              step="any"
              value={latitude}
              onChange={(e) => setLatitude(e.target.value)}
              required
            />
          </div>

          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700" htmlFor="set-location-longitude">
              {t("modal.setLocation.longitude")}
            </label>
            <Input
              id="set-location-longitude"
              type="number"
              step="any"
              value={longitude}
              onChange={(e) => setLongitude(e.target.value)}
              required
            />
          </div>

          {error && (
            <p role="alert" className="text-sm text-red-600">
              {error}
            </p>
          )}

          <div className="flex justify-end gap-2 pt-2">
            <Button type="button" variant="secondary" onClick={onClose}>
              {t("common.cancel")}
            </Button>
            <Button type="submit" disabled={submitting}>
              {submitting ? t("modal.setLocation.saving") : t("modal.setLocation.save")}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
