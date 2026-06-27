import type { Zone, ZonesResponse } from "../types/zone";

export async function fetchZones(city = "madrid"): Promise<Zone[]> {
  const response = await fetch(`/api/parking/ser-zones?city=${city}`);
  if (!response.ok) throw new Error(`Failed to fetch zones: ${response.status}`);
  const data = (await response.json()) as ZonesResponse;
  return data.zones;
}
