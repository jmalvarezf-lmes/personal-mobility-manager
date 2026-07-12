export interface ZoneGeometry {
  type: "Polygon" | "MultiPolygon";
  coordinates: number[][][] | number[][][][];
}

export interface Zone {
  zone_number: string;
  zone_type: string;
  colour: string;
  district: string;
  spot_count: number;
  geometry: ZoneGeometry;
}

export interface Frontier {
  zone_number: string;
  neighbourhood: string;
  geometry: ZoneGeometry;
}

export interface ZonesResponse {
  city: string;
  zones: Zone[];
  frontiers: Frontier[];
}
