import { useState } from "react";
import { useTranslation } from "react-i18next";
import { disconnect } from "../api/serTicketProviders";
import Button from "./ui/Button";
import Card from "./ui/Card";

interface SerProviderRowProps {
  provider: string;
  connected: boolean;
  onConnect: (provider: string) => void;
  onDisconnected: (provider: string, logoutSucceeded: boolean) => void;
}

export default function SerProviderRow({
  provider,
  connected,
  onConnect,
  onDisconnected,
}: SerProviderRowProps) {
  const { t } = useTranslation();
  const [disconnecting, setDisconnecting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [warning, setWarning] = useState<string | null>(null);

  const displayName = t(`page.serProviders.providers.${provider}`, { defaultValue: provider });
  const [logoFailed, setLogoFailed] = useState(false);
  const logoUrl = `/provider-logos/${provider}.webp`;

  async function handleDisconnect() {
    if (!window.confirm(t("page.serProviders.confirmDisconnect", { name: displayName }))) {
      return;
    }
    setError(null);
    setDisconnecting(true);
    try {
      const result = await disconnect(provider);
      setWarning(result.logout_succeeded ? null : t("page.serProviders.logoutNotConfirmed"));
      onDisconnected(provider, result.logout_succeeded);
    } catch (err) {
      setError(err instanceof Error ? err.message : t("page.serProviders.disconnectError"));
    } finally {
      setDisconnecting(false);
    }
  }

  return (
    <Card
      data-testid="ser-provider-row"
      className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between"
    >
      <div className="flex items-center gap-3">
        {!logoFailed && (
          <img
            src={logoUrl}
            alt=""
            aria-hidden="true"
            onError={() => setLogoFailed(true)}
            className="h-10 w-10 flex-shrink-0 rounded object-contain"
          />
        )}
        <div>
          <h3 className="text-lg font-semibold text-gray-800">{displayName}</h3>
          <span
            className={`text-sm ${connected ? "text-green-600" : "text-gray-500"}`}
          >
            {connected ? t("page.serProviders.connected") : t("page.serProviders.notConnected")}
          </span>
          {warning && (
            <p role="alert" className="mt-1 text-sm text-amber-600">
              {warning}
            </p>
          )}
          {error && (
            <p role="alert" className="mt-1 text-sm text-red-600">
              {error}
            </p>
          )}
        </div>
      </div>

      <div>
        {connected ? (
          <Button variant="danger" size="sm" onClick={() => void handleDisconnect()} disabled={disconnecting}>
            {t("page.serProviders.disconnect")}
          </Button>
        ) : (
          <Button size="sm" onClick={() => onConnect(provider)}>
            {t("page.serProviders.connect")}
          </Button>
        )}
      </div>
    </Card>
  );
}
