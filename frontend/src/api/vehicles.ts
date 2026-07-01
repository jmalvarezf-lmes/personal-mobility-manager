import type { VehicleDetail, VehicleListItem } from "../types/vehicle";

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
