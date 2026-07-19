export interface VehicleLocation {
  latitude: number;
  longitude: number;
  recorded_at: string;
}

export interface VehicleListItem {
  vehicle_id: string;
  brand: "toyota" | "generic";
  display_name: string;
  vin: string | null;
  license_plate: string | null;
  location: VehicleLocation | null;
  ambient_label: string | null;
}

export interface ToyotaConfig {
  username: string;
  locale: string;
  password: string;
}

export interface GenericConfig {
  location_token: string;
}

export interface VehicleDetail {
  vehicle_id: string;
  brand: "toyota" | "generic";
  display_name: string;
  vin: string | null;
  license_plate: string | null;
  config: ToyotaConfig | GenericConfig;
  ambient_label: string | null;
}

export interface SerParkingExemption {
  city_code: string | null;
  zone_number: string | null;
}
