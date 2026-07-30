import type {
  SerParkingExemption,
  SerTicketHistoryPage,
  VehicleDetail,
  VehicleListItem,
  VehicleLocationHistoryPage,
} from "../types/vehicle";

export async function listVehicles(): Promise<VehicleListItem[]> {
  const response = await fetch("/api/vehicles", { credentials: "include" });
  if (!response.ok) {
    throw new Error(`Failed to list vehicles: ${response.status}`);
  }
  return (await response.json()) as VehicleListItem[];
}

export async function getVehicle(id: string): Promise<VehicleDetail> {
  const response = await fetch(`/api/vehicles/${id}`, {
    credentials: "include",
  });
  if (!response.ok) {
    throw new Error(`Failed to get vehicle: ${response.status}`);
  }
  return (await response.json()) as VehicleDetail;
}

export async function createVehicle(body: unknown): Promise<VehicleListItem> {
  const response = await fetch("/api/vehicles", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Failed to create vehicle: ${response.status}`);
  }
  return (await response.json()) as VehicleListItem;
}

export async function updateVehicle(
  id: string,
  body: unknown,
): Promise<VehicleDetail> {
  const response = await fetch(`/api/vehicles/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Failed to update vehicle: ${response.status}`);
  }
  return (await response.json()) as VehicleDetail;
}

export async function deleteVehicle(id: string): Promise<void> {
  const response = await fetch(`/api/vehicles/${id}`, {
    method: "DELETE",
    credentials: "include",
  });
  if (!response.ok) {
    throw new Error(`Failed to delete vehicle: ${response.status}`);
  }
}

export async function getVehicleLocationHistory(
  vehicleId: string,
  { limit = 5, offset = 0 }: { limit?: number; offset?: number } = {},
): Promise<VehicleLocationHistoryPage> {
  const params = new URLSearchParams({
    limit: String(limit),
    offset: String(offset),
  });
  const response = await fetch(
    `/api/vehicles/${vehicleId}/locations?${params.toString()}`,
    { credentials: "include" },
  );
  if (!response.ok) {
    throw new Error(
      `Failed to get vehicle location history: ${response.status}`,
    );
  }
  return (await response.json()) as VehicleLocationHistoryPage;
}

export async function pushVehicleLocation(
  vehicleId: string,
  body: { lat: number; lon: number; recorded_at: string },
): Promise<void> {
  const response = await fetch(`/api/vehicles/${vehicleId}/locations`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Failed to push vehicle location: ${response.status}`);
  }
}

export async function getSerTicketHistory(
  vehicleId: string,
  { limit = 5, offset = 0 }: { limit?: number; offset?: number } = {},
): Promise<SerTicketHistoryPage> {
  const params = new URLSearchParams({
    limit: String(limit),
    offset: String(offset),
  });
  const response = await fetch(
    `/api/vehicles/${vehicleId}/ser-tickets?${params.toString()}`,
    { credentials: "include" },
  );
  if (!response.ok) {
    throw new Error(
      `Failed to get SER ticket history: ${response.status}`,
    );
  }
  return (await response.json()) as SerTicketHistoryPage;
}

export async function getSerParkingExemption(
  vehicleId: string,
): Promise<SerParkingExemption> {
  const response = await fetch(
    `/api/vehicles/${vehicleId}/ser-parking-exemptions`,
    { credentials: "include" },
  );
  if (!response.ok) {
    throw new Error(`Failed to get SER parking exemption: ${response.status}`);
  }
  return (await response.json()) as SerParkingExemption;
}

export async function setSerParkingExemption(
  vehicleId: string,
  cityCode: string,
  zoneNumber: string,
): Promise<SerParkingExemption> {
  const response = await fetch(
    `/api/vehicles/${vehicleId}/ser-parking-exemptions`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({ city_code: cityCode, zone_number: zoneNumber }),
    },
  );
  if (!response.ok) {
    const text = await response.text();
    throw new Error(
      text || `Failed to set SER parking exemption: ${response.status}`,
    );
  }
  return (await response.json()) as SerParkingExemption;
}

export async function clearSerParkingExemption(
  vehicleId: string,
): Promise<void> {
  const response = await fetch(
    `/api/vehicles/${vehicleId}/ser-parking-exemptions`,
    { method: "DELETE", credentials: "include" },
  );
  if (!response.ok) {
    throw new Error(
      `Failed to clear SER parking exemption: ${response.status}`,
    );
  }
}
