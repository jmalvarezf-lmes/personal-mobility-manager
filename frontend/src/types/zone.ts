export interface Zone {
  street_name: string;
  zone_type: string;
  colour: string;
  spot_count: number;
  lat: number;
  lng: number;
}

export interface ZonesResponse {
  city: string;
  zones: Zone[];
}
