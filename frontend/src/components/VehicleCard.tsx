import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { deleteVehicle, getVehicle } from "../api/vehicles";
import type { GenericConfig, ToyotaConfig, VehicleDetail, VehicleListItem } from "../types/vehicle";

interface VehicleCardProps {
  vehicle: VehicleListItem;
  onEdit: (detail: VehicleDetail) => void;
  onDeleted: (vehicleId: string) => void;
}

export default function VehicleCard({ vehicle, onEdit, onDeleted }: VehicleCardProps) {
  const { t } = useTranslation();
  const [detail, setDetail] = useState<VehicleDetail | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  useEffect(() => {
    getVehicle(vehicle.vehicle_id)
      .then(setDetail)
      .catch(() => { /* show what we have from the list */ });
  }, [vehicle.vehicle_id]);

  async function handleEdit() {
    try {
      const d = detail ?? await getVehicle(vehicle.vehicle_id);
      onEdit(d);
    } catch (err) {
      setDeleteError(err instanceof Error ? err.message : t("vehicle.edit"));
    }
  }

  async function handleDelete() {
    if (!window.confirm(t("vehicle.confirmDelete", { name: vehicle.display_name }))) {
      return;
    }
    try {
      await deleteVehicle(vehicle.vehicle_id);
      onDeleted(vehicle.vehicle_id);
    } catch (err) {
      setDeleteError(err instanceof Error ? err.message : t("vehicle.delete"));
    }
  }

  const toyotaConfig = detail?.brand === "toyota" ? (detail.config as ToyotaConfig) : null;
  const genericConfig = detail?.brand === "generic" ? (detail.config as GenericConfig) : null;

  return (
    <div data-testid="vehicle-card" className="rounded border border-gray-200 bg-white p-4 shadow-sm">
      <div className="mb-2 flex items-center justify-between">
        <h3 className="text-lg font-semibold text-gray-800">{vehicle.display_name}</h3>
        <span className="rounded bg-blue-100 px-2 py-0.5 text-xs font-medium text-blue-700 capitalize">
          {vehicle.brand}
        </span>
      </div>

      {vehicle.brand === "toyota" && vehicle.vin && (
        <p className="text-sm text-gray-500">{t("vehicle.vin")}: {vehicle.vin}</p>
      )}

      {toyotaConfig && (
        <div className="mt-1 space-y-0.5 text-sm text-gray-600">
          <p>{t("vehicle.username")}: {toyotaConfig.username}</p>
          <p>{t("vehicle.locale")}: {toyotaConfig.locale}</p>
          <p>{t("vehicle.password")}: {toyotaConfig.password}</p>
        </div>
      )}

      {genericConfig && (
        <div className="mt-1 text-sm text-gray-600">
          <p className="break-all">
            {t("vehicle.pushUrl")}:{" "}
            {`${window.location.origin}/api/vehicles/${genericConfig.location_token}/location`}
          </p>
        </div>
      )}

      <div className="mt-2 text-sm text-gray-600">
        {vehicle.location ? (
          <p>
            {t("vehicle.location")}: {vehicle.location.latitude.toFixed(5)},{" "}
            {vehicle.location.longitude.toFixed(5)}
          </p>
        ) : (
          <p className="italic text-gray-400">{t("vehicle.noLocation")}</p>
        )}
      </div>

      {deleteError && (
        <p role="alert" className="mt-2 text-sm text-red-600">
          {deleteError}
        </p>
      )}

      <div className="mt-3 flex gap-2">
        <button
          onClick={() => void handleEdit()}
          className="rounded bg-gray-100 px-3 py-1 text-sm hover:bg-gray-200"
        >
          {t("vehicle.edit")}
        </button>
        <button
          onClick={() => void handleDelete()}
          className="rounded bg-red-100 px-3 py-1 text-sm text-red-700 hover:bg-red-200"
        >
          {t("vehicle.delete")}
        </button>
      </div>
    </div>
  );
}
