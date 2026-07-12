import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { fetchOsmTileUrl } from "../api/config";
import { fetchZones } from "../api/zones";
import Nav from "../components/Nav";
import ZoneMap from "../components/ZoneMap";
import type { Frontier, Zone } from "../types/zone";

export default function MapPage() {
  const { t } = useTranslation();
  const [zones, setZones] = useState<Zone[]>([]);
  const [frontiers, setFrontiers] = useState<Frontier[]>([]);
  const [tileUrl, setTileUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      try {
        const [fetchedTileUrl, fetchedZonesResult] = await Promise.all([
          fetchOsmTileUrl(),
          fetchZones(),
        ]);
        setTileUrl(fetchedTileUrl);
        setZones(fetchedZonesResult.zones);
        setFrontiers(fetchedZonesResult.frontiers);
      } catch (err) {
        setError(err instanceof Error ? err.message : t("page.map.loading"));
      } finally {
        setLoading(false);
      }
    }
    void load();
  }, [t]);

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center text-gray-600">
        {t("page.map.loading")}
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
        <ZoneMap zones={zones} frontiers={frontiers} tileUrl={tileUrl} />
      </div>
    </div>
  );
}
