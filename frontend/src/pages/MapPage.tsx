import { useEffect, useState } from "react";
import { fetchOsmTileUrl } from "../api/config";
import { fetchZones } from "../api/zones";
import Nav from "../components/Nav";
import ZoneMap from "../components/ZoneMap";
import type { Zone } from "../types/zone";

export default function MapPage() {
  const [zones, setZones] = useState<Zone[]>([]);
  const [tileUrl, setTileUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      try {
        const [fetchedTileUrl, fetchedZones] = await Promise.all([
          fetchOsmTileUrl(),
          fetchZones(),
        ]);
        setTileUrl(fetchedTileUrl);
        setZones(fetchedZones);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load map data");
      } finally {
        setLoading(false);
      }
    }
    void load();
  }, []);

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center text-gray-600">
        Cargando zonas…
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex h-screen items-center justify-center text-red-600">
        {error}
      </div>
    );
  }

  return (
    <div className="flex h-screen flex-col">
      <Nav />
      <div className="flex-1">
        <ZoneMap zones={zones} tileUrl={tileUrl} />
      </div>
    </div>
  );
}
