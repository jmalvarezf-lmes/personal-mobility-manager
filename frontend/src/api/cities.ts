import type { City } from "../types/city";

export async function listCities(): Promise<City[]> {
  const response = await fetch("/api/cities");
  if (!response.ok) {
    throw new Error(`Failed to list cities: ${response.status}`);
  }
  return (await response.json()) as City[];
}
