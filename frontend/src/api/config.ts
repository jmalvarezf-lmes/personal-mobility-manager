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
