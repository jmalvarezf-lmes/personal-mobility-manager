import { useState } from "react";
import { updateVehicle } from "../api/vehicles";
import type { GenericConfig, ToyotaConfig, VehicleDetail } from "../types/vehicle";

function isToyotaConfig(config: ToyotaConfig | GenericConfig): config is ToyotaConfig {
  return "username" in config;
}

interface EditVehicleModalProps {
  vehicle: VehicleDetail;
  onClose: () => void;
  onUpdated: (updated: VehicleDetail) => void;
}

export default function EditVehicleModal({ vehicle, onClose, onUpdated }: EditVehicleModalProps) {
  const toyotaCfg = isToyotaConfig(vehicle.config) ? vehicle.config : null;

  const [displayName, setDisplayName] = useState(vehicle.display_name);
  const [username, setUsername] = useState(toyotaCfg?.username ?? "");
  const [locale, setLocale] = useState(toyotaCfg?.locale ?? "");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const body =
        vehicle.brand === "toyota"
          ? {
              brand: "toyota",
              display_name: displayName,
              username,
              locale,
              ...(password ? { password } : {}),
            }
          : { brand: "generic", display_name: displayName };
      const updated = await updateVehicle(vehicle.vehicle_id, body);
      onUpdated(updated);
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update vehicle");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Edit Vehicle"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
    >
      <div className="w-full max-w-md rounded bg-white p-6 shadow-lg">
        <h2 className="mb-4 text-lg font-semibold">Edit Vehicle</h2>
        <form onSubmit={(e) => void handleSubmit(e)} className="space-y-3">
          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700" htmlFor="edit-display-name">
              Display Name
            </label>
            <input
              id="edit-display-name"
              type="text"
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              required
              className="w-full rounded border border-gray-300 px-3 py-2 text-sm"
            />
          </div>

          {vehicle.brand === "toyota" && (
            <>
              {vehicle.vin && (
                <div>
                  <span className="text-sm text-gray-500">VIN: {vehicle.vin}</span>
                </div>
              )}
              <div>
                <label className="mb-1 block text-sm font-medium text-gray-700" htmlFor="edit-username">
                  Username
                </label>
                <input
                  id="edit-username"
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  required
                  className="w-full rounded border border-gray-300 px-3 py-2 text-sm"
                />
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium text-gray-700" htmlFor="edit-locale">
                  Locale
                </label>
                <input
                  id="edit-locale"
                  type="text"
                  value={locale}
                  onChange={(e) => setLocale(e.target.value)}
                  required
                  className="w-full rounded border border-gray-300 px-3 py-2 text-sm"
                />
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium text-gray-700" htmlFor="edit-password">
                  New Password <span className="text-xs text-gray-400">(leave blank to keep current)</span>
                </label>
                <input
                  id="edit-password"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full rounded border border-gray-300 px-3 py-2 text-sm"
                />
              </div>
            </>
          )}

          {error && (
            <p role="alert" className="text-sm text-red-600">
              {error}
            </p>
          )}

          <div className="flex justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="rounded bg-gray-100 px-4 py-2 text-sm hover:bg-gray-200"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={submitting}
              className="rounded bg-blue-600 px-4 py-2 text-sm text-white hover:bg-blue-700 disabled:opacity-50"
            >
              {submitting ? "Saving…" : "Save"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
