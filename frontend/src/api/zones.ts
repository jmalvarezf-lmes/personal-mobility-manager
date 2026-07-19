import type { Frontier, Zone, ZoneOption, ZoneOptionsResponse, ZonesResponse } from "../types/zone";

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

// Lightweight sibling of fetchZones: only zone_number + neighbourhood pairs,
// no geometry reprojection. Used by the SER parking exemption picker's zone
// <select>, which does not need to render any polygon — fetchZones/GET
// /parking/ser-zones is far heavier (full GeoJSON per zone/frontier row) and
// was causing a multi-second delay before an already-known selection showed
// as selected.
//
// Requests `sort=asc` explicitly rather than relying on the server default,
// so the picker's neighbourhood options are always alphabetically ordered.
export async function fetchZoneOptions(city: string): Promise<ZoneOption[]> {
  const response = await fetch(`/api/parking/ser-zone-options?city=${city}&sort=asc`);
  if (!response.ok) throw new Error(`Failed to fetch zone options: ${response.status}`);
  const data = (await response.json()) as ZoneOptionsResponse;
  return data.options;
}
