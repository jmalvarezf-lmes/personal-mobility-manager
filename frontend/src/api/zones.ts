import type { Frontier, Zone, ZonesResponse } from "../types/zone";

export interface FetchZonesResult {
  zones: Zone[];
  frontiers: Frontier[];
}

export async function fetchZones(city = "madrid"): Promise<FetchZonesResult> {
  const response = await fetch(`/api/parking/ser-zones?city=${city}`);
  if (!response.ok) throw new Error(`Failed to fetch zones: ${response.status}`);
  const data = (await response.json()) as ZonesResponse;
  return { zones: data.zones, frontiers: data.frontiers };
}
