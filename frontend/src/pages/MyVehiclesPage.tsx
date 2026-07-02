import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { listVehicles } from "../api/vehicles";
import AddVehicleModal from "../components/AddVehicleModal";
import EditVehicleModal from "../components/EditVehicleModal";
import Nav from "../components/Nav";
import VehicleCard from "../components/VehicleCard";
import VehicleMap from "../components/VehicleMap";
import type { VehicleDetail, VehicleListItem } from "../types/vehicle";

export default function MyVehiclesPage() {
  const { t } = useTranslation();
  const [vehicles, setVehicles] = useState<VehicleListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showAdd, setShowAdd] = useState(false);
  const [editVehicle, setEditVehicle] = useState<VehicleDetail | null>(null);

  useEffect(() => {
    async function load() {
      try {
        const data = await listVehicles();
        setVehicles(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : t("page.myVehicles.loading"));
      } finally {
        setLoading(false);
      }
    }
    void load();
  }, [t]);

  function handleCreated(vehicle: VehicleListItem) {
    setVehicles((prev) => [...prev, { ...vehicle, location: vehicle.location ?? null }]);
  }

  function handleDeleted(vehicleId: string) {
    setVehicles((prev) => prev.filter((v) => v.vehicle_id !== vehicleId));
  }

  function handleUpdated(updated: VehicleDetail) {
    setVehicles((prev) =>
      prev.map((v) =>
        v.vehicle_id === updated.vehicle_id
          ? {
              ...v,
              display_name: updated.display_name,
              brand: updated.brand,
              vin: updated.vin,
            }
          : v,
      ),
    );
  }

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center text-gray-600">
        {t("page.myVehicles.loading")}
      </div>
    );
  }

  return (
    <div className="flex h-screen flex-col">
      <Nav />
      <div className="flex-1 overflow-auto p-6">
        <div className="mb-4 flex items-center justify-between">
          <h1 className="text-2xl font-bold text-gray-800">{t("page.myVehicles.title")}</h1>
          <button
            onClick={() => setShowAdd(true)}
            className="rounded bg-blue-600 px-4 py-2 text-sm text-white hover:bg-blue-700"
          >
            {t("page.myVehicles.add")}
          </button>
        </div>

        {error && (
          <p role="alert" className="mb-4 text-red-600">
            {error}
          </p>
        )}

        {vehicles.length > 0 && (
          <div className="mb-6 h-64 overflow-hidden rounded border border-gray-200">
            <VehicleMap vehicles={vehicles} />
          </div>
        )}

        {vehicles.length === 0 && !error && (
          <p className="text-gray-500">{t("page.myVehicles.empty")}</p>
        )}

        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {vehicles.map((v) => (
            <VehicleCard
              key={v.vehicle_id}
              vehicle={v}
              onEdit={(detail) => setEditVehicle(detail)}
              onDeleted={handleDeleted}
            />
          ))}
        </div>
      </div>

      {showAdd && (
        <AddVehicleModal
          onClose={() => setShowAdd(false)}
          onCreated={handleCreated}
        />
      )}

      {editVehicle && (
        <EditVehicleModal
          vehicle={editVehicle}
          onClose={() => setEditVehicle(null)}
          onUpdated={handleUpdated}
        />
      )}
    </div>
  );
}
