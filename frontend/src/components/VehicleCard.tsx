import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { deleteVehicle, getVehicle } from "../api/vehicles";
import type { GenericConfig, ToyotaConfig, VehicleDetail, VehicleListItem } from "../types/vehicle";
import AmbientLabelIcon from "./AmbientLabelIcon";
import Button from "./ui/Button";
import Card from "./ui/Card";

interface VehicleCardProps {
  vehicle: VehicleListItem;
  onEdit: (detail: VehicleDetail) => void;
  onDeleted: (vehicleId: string) => void;
  onViewHistory: (vehicle: VehicleListItem) => void;
  onViewSerTickets: (vehicle: VehicleListItem) => void;
}

export default function VehicleCard({
  vehicle,
  onEdit,
  onDeleted,
  onViewHistory,
  onViewSerTickets,
}: VehicleCardProps) {
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
    <Card data-testid="vehicle-card">
      <div className="mb-2 flex items-center justify-between">
        <h3 className="text-lg font-semibold text-gray-800">{vehicle.display_name}</h3>
        <div className="flex items-center gap-2">
          <AmbientLabelIcon label={vehicle.ambient_label} />
          <span className="rounded bg-blue-100 px-2 py-0.5 text-xs font-medium text-blue-700 capitalize">
            {vehicle.brand}
          </span>
        </div>
      </div>

      {vehicle.brand === "toyota" && vehicle.vin && (
        <p className="text-sm text-gray-500">{t("vehicle.vin")}: {vehicle.vin}</p>
      )}

      <div className="mt-1 text-sm text-gray-500">
        {vehicle.license_plate ? (
          <p>{t("vehicle.licensePlate")}: {vehicle.license_plate}</p>
        ) : (
          <p className="italic text-gray-400">{t("vehicle.noLicensePlate")}</p>
        )}
      </div>

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

      <div className="mt-2 flex items-center justify-between gap-2 text-sm text-gray-600">
        {vehicle.location ? (
          <p>
            {t("vehicle.location")}: {vehicle.location.latitude.toFixed(5)},{" "}
            {vehicle.location.longitude.toFixed(5)}
          </p>
        ) : (
          <p className="italic text-gray-400">{t("vehicle.noLocation")}</p>
        )}
        <div className="flex shrink-0 gap-2">
          {vehicle.location && (
            <Button variant="secondary" size="sm" className="shrink-0" onClick={() => onViewHistory(vehicle)}>
              {t("vehicle.viewHistory")}
            </Button>
          )}
          {vehicle.has_ser_tickets && (
            <Button
              variant="secondary"
              size="sm"
              className="shrink-0"
              onClick={() => onViewSerTickets(vehicle)}
            >
              {t("vehicle.viewSerTickets")}
            </Button>
          )}
        </div>
      </div>

      {deleteError && (
        <p role="alert" className="mt-2 text-sm text-red-600">
          {deleteError}
        </p>
      )}

      <div className="mt-3 flex gap-2">
        <Button variant="secondary" size="sm" onClick={() => void handleEdit()}>
          {t("vehicle.edit")}
        </Button>
        <Button variant="danger" size="sm" onClick={() => void handleDelete()}>
          {t("vehicle.delete")}
        </Button>
      </div>
    </Card>
  );
}
