import { useState } from "react";
import { useTranslation } from "react-i18next";
import { disconnectChannel } from "../../api/notifications";
import Button from "../ui/Button";
import Card from "../ui/Card";

interface NotificationChannelRowProps {
  channel: string;
  connected: boolean;
  supported: boolean;
  onConnect: (channel: string) => void;
  onDisconnected: (channel: string) => void;
}

export default function NotificationChannelRow({
  channel,
  connected,
  supported,
  onConnect,
  onDisconnected,
}: NotificationChannelRowProps) {
  const { t } = useTranslation();
  const [disconnecting, setDisconnecting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const displayName = t(`page.notificationChannels.channels.${channel}`, { defaultValue: channel });

  async function handleDisconnect() {
    if (!window.confirm(t("page.notificationChannels.confirmDisconnect", { name: displayName }))) {
      return;
    }
    setError(null);
    setDisconnecting(true);
    try {
      await disconnectChannel(channel);
      onDisconnected(channel);
    } catch (err) {
      setError(err instanceof Error ? err.message : t("page.notificationChannels.disconnectError"));
    } finally {
      setDisconnecting(false);
    }
  }

  return (
    <Card
      data-testid="notification-channel-row"
      className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between"
    >
      <div>
        <h3 className="text-lg font-semibold text-gray-800">{displayName}</h3>
        <span className={`text-sm ${connected ? "text-green-600" : "text-gray-500"}`}>
          {connected
            ? t("page.notificationChannels.connected")
            : supported
              ? t("page.notificationChannels.notConnected")
              : t("page.notificationChannels.notSupported")}
        </span>
        {error && (
          <p role="alert" className="mt-1 text-sm text-red-600">
            {error}
          </p>
        )}
      </div>

      <div>
        {connected ? (
          <Button variant="danger" size="sm" onClick={() => void handleDisconnect()} disabled={disconnecting}>
            {t("page.notificationChannels.disconnect")}
          </Button>
        ) : (
          <Button size="sm" onClick={() => onConnect(channel)} disabled={!supported}>
            {t("page.notificationChannels.connect")}
          </Button>
        )}
      </div>
    </Card>
  );
}
