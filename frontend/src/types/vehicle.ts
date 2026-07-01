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
  location: VehicleLocation | null;
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
  config: ToyotaConfig | GenericConfig;
}
