export interface VehicleLocation {
  latitude: number;
  longitude: number;
  recorded_at: string;
}

export interface VehicleLocationHistoryPage {
  items: VehicleLocation[];
  has_more: boolean;
}

export interface SerTicket {
  id: string;
  latitude: number | null;
  longitude: number | null;
  start_date: string;
  end_date: string;
  city_code: string | null;
  city_name: string | null;
  zone_number: string | null;
  auto_created: boolean | null;
}

export interface SerTicketHistoryPage {
  items: SerTicket[];
  has_more: boolean;
}

export interface VehicleListItem {
  vehicle_id: string;
  brand: "toyota" | "generic";
  display_name: string;
  vin: string | null;
  license_plate: string | null;
  location: VehicleLocation | null;
  ambient_label: string | null;
  has_ser_tickets: boolean;
  is_owner: boolean;
}

export interface ToyotaConfig {
  username: string;
  locale: string;
  password: string;
}

export interface GenericConfig {
  location_token: string;
}

export interface RedactedConfig {
  redacted: true;
}

export type VehicleConfig = ToyotaConfig | GenericConfig | RedactedConfig;

export function isRedactedConfig(
  config: VehicleConfig,
): config is RedactedConfig {
  return "redacted" in config && config.redacted === true;
}

export interface VehicleDetail {
  vehicle_id: string;
  brand: "toyota" | "generic";
  display_name: string;
  vin: string | null;
  license_plate: string | null;
  config: VehicleConfig;
  ambient_label: string | null;
  is_owner: boolean;
}

export interface VehicleSharee {
  user_id: string;
  display_name: string;
  email: string;
  created_at: string;
}

export interface VehicleSharesResponse {
  vehicle_id: string;
  sharees: VehicleSharee[];
}

export interface SerParkingExemption {
  city_code: string | null;
  zone_number: string | null;
}
