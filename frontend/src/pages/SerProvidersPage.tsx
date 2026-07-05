import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { getConnections } from "../api/serTicketProviders";
import ConnectSerProviderModal from "../components/ConnectSerProviderModal";
import Nav from "../components/Nav";
import SerProviderRow from "../components/SerProviderRow";

// Hardcoded known-provider list — mirrors AddVehicleModal's convention of
// hardcoding small, slow-changing enumerations client-side rather than
// fetching them from an API.
const KNOWN_PROVIDERS = ["elparking"];

export default function SerProvidersPage() {
  const { t } = useTranslation();
  const [connectedProviders, setConnectedProviders] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [connectingProvider, setConnectingProvider] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      try {
        const data = await getConnections();
        setConnectedProviders(data.providers);
      } catch (err) {
        setError(err instanceof Error ? err.message : t("page.serProviders.loading"));
      } finally {
        setLoading(false);
      }
    }
    void load();
  }, [t]);

  function handleConnected(provider: string) {
    setConnectedProviders((prev) => (prev.includes(provider) ? prev : [...prev, provider]));
  }

  function handleDisconnected(provider: string) {
    setConnectedProviders((prev) => prev.filter((p) => p !== provider));
  }

  const connectingProviderDisplayName = connectingProvider
    ? t(`page.serProviders.providers.${connectingProvider}`, { defaultValue: connectingProvider })
    : "";

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center text-gray-600">
        {t("page.serProviders.loading")}
      </div>
    );
  }

  return (
    <div className="flex h-screen flex-col">
      <Nav />
      <div className="flex-1 overflow-auto p-6">
        <h1 className="mb-4 text-2xl font-bold text-gray-800">{t("page.serProviders.title")}</h1>

        {error && (
          <p role="alert" className="mb-4 text-red-600">
            {error}
          </p>
        )}

        <div className="space-y-3">
          {KNOWN_PROVIDERS.map((provider) => (
            <SerProviderRow
              key={provider}
              provider={provider}
              connected={connectedProviders.includes(provider)}
              onConnect={setConnectingProvider}
              onDisconnected={handleDisconnected}
            />
          ))}
        </div>
      </div>

      {connectingProvider && (
        <ConnectSerProviderModal
          provider={connectingProvider}
          providerDisplayName={connectingProviderDisplayName}
          onClose={() => setConnectingProvider(null)}
          onConnected={handleConnected}
        />
      )}
    </div>
  );
}
