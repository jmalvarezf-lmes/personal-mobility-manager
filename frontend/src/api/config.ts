export async function fetchOsmTileUrl(): Promise<string | null> {
  try {
    const response = await fetch("/api/config");
    if (!response.ok) return null;
    const data = (await response.json()) as { osm_tile_url: string | null };
    return data.osm_tile_url;
  } catch {
    return null;
  }
}

export async function fetchToyotaLocale(): Promise<string | null> {
  try {
    const response = await fetch("/api/config");
    if (!response.ok) return null;
    const data = (await response.json()) as { toyota_locale: string };
    return data.toyota_locale;
  } catch {
    return null;
  }
}
