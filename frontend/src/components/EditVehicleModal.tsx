import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { listCities } from "../api/cities";
import {
  clearSerParkingExemption,
  getSerParkingExemption,
  setSerParkingExemption,
  updateVehicle,
} from "../api/vehicles";
import { fetchZoneOptions } from "../api/zones";
import type { City } from "../types/city";
import type { GenericConfig, ToyotaConfig, VehicleDetail } from "../types/vehicle";
import type { ZoneOption } from "../types/zone";

function isToyotaConfig(config: ToyotaConfig | GenericConfig): config is ToyotaConfig {
  return "username" in config;
}

interface EditVehicleModalProps {
  vehicle: VehicleDetail;
  onClose: () => void;
  onUpdated: (updated: VehicleDetail) => void;
}

export default function EditVehicleModal({ vehicle, onClose, onUpdated }: EditVehicleModalProps) {
  const { t } = useTranslation();
  const toyotaCfg = isToyotaConfig(vehicle.config) ? vehicle.config : null;

  const [displayName, setDisplayName] = useState(vehicle.display_name);
  const [username, setUsername] = useState(toyotaCfg?.username ?? "");
  const [locale, setLocale] = useState(toyotaCfg?.locale ?? "");
  const [password, setPassword] = useState("");
  const [licenseplate, setLicenseplate] = useState(vehicle.license_plate ?? "");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  // ---------------------------------------------------------------------
  // SER parking exemption picker (city -> zone, labeled by neighbourhood)
  //
  // There is a single save action for the whole dialog (the form's "Save"
  // button / handleSubmit): the picker only holds local state until submit,
  // which persists both the vehicle fields and the exemption together. See
  // handleSubmit for the reconciliation logic.
  // ---------------------------------------------------------------------
  const [cities, setCities] = useState<City[]>([]);
  const [zoneOptions, setZoneOptions] = useState<ZoneOption[]>([]);
  const [exemptionCity, setExemptionCity] = useState("");
  const [exemptionZone, setExemptionZone] = useState("");
  // Whether the vehicle already had a stored exemption when the modal
  // opened — needed at submit time to tell "the picker is now empty because
  // the user cleared it" (call DELETE) apart from "there was never one"
  // (no exemption API call at all).
  const [exemptionExistedInitially, setExemptionExistedInitially] = useState(false);
  // True while the initial getSerParkingExemption call — and, if it
  // returned a city, the resulting zone-options fetch — are in flight. Used
  // to show an honest "Loading…" state instead of a zone <select> that
  // looks unselected merely because its options haven't arrived yet.
  const [exemptionInitialLoading, setExemptionInitialLoading] = useState(true);
  const [zoneOptionsLoading, setZoneOptionsLoading] = useState(false);
  const exemptionLoading = exemptionInitialLoading || zoneOptionsLoading;

  useEffect(() => {
    let cancelled = false;

    void listCities()
      .then((loaded) => {
        if (!cancelled) setCities(loaded);
      })
      .catch(() => {
        if (!cancelled) setCities([]);
      });

    void (async () => {
      try {
        const exemption = await getSerParkingExemption(vehicle.vehicle_id);
        if (cancelled) return;
        setExemptionExistedInitially(Boolean(exemption.city_code && exemption.zone_number));
        if (exemption.zone_number) setExemptionZone(exemption.zone_number);
        if (exemption.city_code) {
          setExemptionCity(exemption.city_code);
          try {
            const options = await fetchZoneOptions(exemption.city_code);
            if (!cancelled) setZoneOptions(options);
          } catch {
            if (!cancelled) setZoneOptions([]);
          }
        }
      } catch {
        // No stored exemption, or the lookup failed — leave the picker empty.
      } finally {
        if (!cancelled) setExemptionInitialLoading(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [vehicle.vehicle_id]);

  function handleExemptionCityChange(cityCode: string) {
    setExemptionCity(cityCode);
    setExemptionZone("");
    setZoneOptions([]);
    if (!cityCode) return;
    setZoneOptionsLoading(true);
    void fetchZoneOptions(cityCode)
      .then(setZoneOptions)
      .catch(() => setZoneOptions([]))
      .finally(() => setZoneOptionsLoading(false));
  }

  // Local-only reset — the actual DELETE (if one is needed) happens as part
  // of the single save action in handleSubmit, not here.
  function handleClearExemption() {
    setExemptionCity("");
    setExemptionZone("");
    setZoneOptions([]);
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const licensePlateValue = licenseplate === "" ? null : licenseplate;
      const body =
        vehicle.brand === "toyota"
          ? {
              brand: "toyota",
              display_name: displayName,
              username,
              locale,
              license_plate: licensePlateValue,
              ...(password ? { password } : {}),
            }
          : { brand: "generic", display_name: displayName, license_plate: licensePlateValue };
      const updated = await updateVehicle(vehicle.vehicle_id, body);

      try {
        if (exemptionCity && exemptionZone) {
          await setSerParkingExemption(vehicle.vehicle_id, exemptionCity, exemptionZone);
        } else if (exemptionExistedInitially) {
          await clearSerParkingExemption(vehicle.vehicle_id);
        }
      } catch (exemptionErr) {
        setError(
          exemptionErr instanceof Error
            ? exemptionErr.message
            : t("modal.editVehicle.serExemption.saveError"),
        );
        return;
      }

      onUpdated(updated);
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("modal.editVehicle.title"));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={t("modal.editVehicle.title")}
      className="fixed inset-0 z-[1001] flex items-center justify-center bg-black/40"
    >
      <div className="w-full max-w-md rounded bg-white p-6 shadow-lg">
        <h2 className="mb-4 text-lg font-semibold">{t("modal.editVehicle.title")}</h2>
        <form onSubmit={(e) => void handleSubmit(e)} className="space-y-3">
          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700" htmlFor="edit-display-name">
              {t("common.displayName")}
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

          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700" htmlFor="edit-license-plate">
              {t("vehicle.licensePlate")}{" "}
              <span className="text-xs text-gray-400">{t("modal.editVehicle.keepBlank")}</span>
            </label>
            <input
              id="edit-license-plate"
              type="text"
              value={licenseplate}
              onChange={(e) => setLicenseplate(e.target.value)}
              maxLength={20}
              placeholder={t("vehicle.noLicensePlate")}
              className="w-full rounded border border-gray-300 px-3 py-2 text-sm"
            />
          </div>

          {vehicle.brand === "toyota" && (
            <>
              {vehicle.vin && (
                <div>
                  <span className="text-sm text-gray-500">{t("vehicle.vin")}: {vehicle.vin}</span>
                </div>
              )}
              <div>
                <label className="mb-1 block text-sm font-medium text-gray-700" htmlFor="edit-username">
                  {t("common.username")}
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
                  {t("common.locale")}
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
                  {t("modal.editVehicle.newPassword")}{" "}
                  <span className="text-xs text-gray-400">{t("modal.editVehicle.keepBlank")}</span>
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

          <div className="border-t border-gray-200 pt-3">
            <h3 className="mb-2 text-sm font-semibold text-gray-700">
              {t("modal.editVehicle.serExemption.title")}
            </h3>
            <div className="space-y-2">
              <div>
                <label className="mb-1 block text-sm font-medium text-gray-700" htmlFor="exemption-city">
                  {t("modal.editVehicle.serExemption.cityLabel")}
                </label>
                <select
                  id="exemption-city"
                  value={exemptionCity}
                  onChange={(e) => handleExemptionCityChange(e.target.value)}
                  className="w-full rounded border border-gray-300 px-3 py-2 text-sm"
                >
                  <option value="">{t("modal.editVehicle.serExemption.selectCity")}</option>
                  {cities.map((city) => (
                    <option key={city.code} value={city.code}>
                      {city.name}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium text-gray-700" htmlFor="exemption-zone">
                  {t("modal.editVehicle.serExemption.zoneLabel")}
                </label>
                <select
                  id="exemption-zone"
                  value={exemptionLoading ? "" : exemptionZone}
                  onChange={(e) => setExemptionZone(e.target.value)}
                  disabled={!exemptionCity || exemptionLoading || zoneOptions.length === 0}
                  className="w-full rounded border border-gray-300 px-3 py-2 text-sm disabled:bg-gray-100"
                >
                  <option value="">
                    {exemptionLoading
                      ? t("modal.editVehicle.serExemption.loading")
                      : exemptionCity
                        ? t("modal.editVehicle.serExemption.selectZone")
                        : t("modal.editVehicle.serExemption.selectCityFirst")}
                  </option>
                  {!exemptionLoading &&
                    zoneOptions.map((option) => (
                      <option key={option.zone_number} value={option.zone_number}>
                        {option.neighbourhood}
                      </option>
                    ))}
                </select>
              </div>

              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={handleClearExemption}
                  disabled={submitting || (!exemptionCity && !exemptionZone)}
                  className="rounded bg-gray-100 px-3 py-1.5 text-xs hover:bg-gray-200 disabled:opacity-50"
                >
                  {t("modal.editVehicle.serExemption.clear")}
                </button>
              </div>
            </div>
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="rounded bg-gray-100 px-4 py-2 text-sm hover:bg-gray-200"
            >
              {t("common.cancel")}
            </button>
            <button
              type="submit"
              disabled={submitting}
              className="rounded bg-blue-600 px-4 py-2 text-sm text-white hover:bg-blue-700 disabled:opacity-50"
            >
              {submitting ? t("modal.editVehicle.saving") : t("modal.editVehicle.save")}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
