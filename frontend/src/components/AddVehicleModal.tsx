import { useState } from "react";
import { createVehicle } from "../api/vehicles";
import type { VehicleListItem } from "../types/vehicle";

interface AddVehicleModalProps {
  onClose: () => void;
  onCreated: (vehicle: VehicleListItem) => void;
}

export default function AddVehicleModal({ onClose, onCreated }: AddVehicleModalProps) {
  const [brand, setBrand] = useState<"toyota" | "generic">("generic");
  const [displayName, setDisplayName] = useState("");
  const [vin, setVin] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [locale, setLocale] = useState("en_GB");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const body =
        brand === "toyota"
          ? { brand, display_name: displayName, vin, username, password, locale }
          : { brand, display_name: displayName };
      const result = await createVehicle(body);
      onCreated(result);
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to add vehicle");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Add Vehicle"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
    >
      <div className="w-full max-w-md rounded bg-white p-6 shadow-lg">
        <h2 className="mb-4 text-lg font-semibold">Add Vehicle</h2>
        <form onSubmit={(e) => void handleSubmit(e)} className="space-y-3">
          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700" htmlFor="brand">
              Brand
            </label>
            <select
              id="brand"
              value={brand}
              onChange={(e) => setBrand(e.target.value as "toyota" | "generic")}
              className="w-full rounded border border-gray-300 px-3 py-2 text-sm"
            >
              <option value="generic">Generic</option>
              <option value="toyota">Toyota</option>
            </select>
          </div>

          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700" htmlFor="display-name">
              Display Name
            </label>
            <input
              id="display-name"
              type="text"
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              required
              className="w-full rounded border border-gray-300 px-3 py-2 text-sm"
            />
          </div>

          {brand === "toyota" && (
            <>
              <div>
                <label className="mb-1 block text-sm font-medium text-gray-700" htmlFor="vin">
                  VIN
                </label>
                <input
                  id="vin"
                  type="text"
                  value={vin}
                  onChange={(e) => setVin(e.target.value)}
                  required
                  className="w-full rounded border border-gray-300 px-3 py-2 text-sm"
                />
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium text-gray-700" htmlFor="username">
                  Username
                </label>
                <input
                  id="username"
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  required
                  className="w-full rounded border border-gray-300 px-3 py-2 text-sm"
                />
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium text-gray-700" htmlFor="password">
                  Password
                </label>
                <input
                  id="password"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  className="w-full rounded border border-gray-300 px-3 py-2 text-sm"
                />
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium text-gray-700" htmlFor="locale">
                  Locale
                </label>
                <input
                  id="locale"
                  type="text"
                  value={locale}
                  onChange={(e) => setLocale(e.target.value)}
                  required
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
              {submitting ? "Adding…" : "Add"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
