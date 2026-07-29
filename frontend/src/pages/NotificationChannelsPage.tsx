import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { getAvailableChannels, getConfiguredChannels } from "../api/notifications";
import Nav from "../components/Nav";
import NotificationChannelRow from "../components/notificationChannels/NotificationChannelRow";
import { CONNECT_FLOW_REGISTRY } from "../components/notificationChannels/registry";
import PageHeader from "../components/ui/PageHeader";

export default function NotificationChannelsPage() {
  const { t } = useTranslation();
  const [availableChannels, setAvailableChannels] = useState<string[]>([]);
  const [connectedChannels, setConnectedChannels] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [connectingChannel, setConnectingChannel] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      try {
        const [available, configured] = await Promise.all([
          getAvailableChannels(),
          getConfiguredChannels(),
        ]);
        setAvailableChannels(available.channels);
        setConnectedChannels(configured.channels);
      } catch (err) {
        setError(err instanceof Error ? err.message : t("page.notificationChannels.loading"));
      } finally {
        setLoading(false);
      }
    }
    void load();
  }, [t]);

  function handleConnected(channel: string) {
    setConnectedChannels((prev) => (prev.includes(channel) ? prev : [...prev, channel]));
    setConnectingChannel(null);
  }

  function handleDisconnected(channel: string) {
    setConnectedChannels((prev) => prev.filter((c) => c !== channel));
  }

  const ConnectFlowComponent = connectingChannel ? CONNECT_FLOW_REGISTRY[connectingChannel] : undefined;

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center text-gray-600">
        {t("page.notificationChannels.loading")}
      </div>
    );
  }

  return (
    <div className="flex h-screen flex-col">
      <Nav />
      <div className="flex-1 overflow-auto p-6">
        <PageHeader title={t("page.notificationChannels.title")} />

        {error && (
          <p role="alert" className="mb-4 text-red-600">
            {error}
          </p>
        )}

        <div className="space-y-3">
          {availableChannels.map((channel) => (
            <NotificationChannelRow
              key={channel}
              channel={channel}
              connected={connectedChannels.includes(channel)}
              supported={channel in CONNECT_FLOW_REGISTRY}
              onConnect={setConnectingChannel}
              onDisconnected={handleDisconnected}
            />
          ))}
        </div>
      </div>

      {connectingChannel && ConnectFlowComponent && (
        <ConnectFlowComponent
          onClose={() => setConnectingChannel(null)}
          onConnected={handleConnected}
        />
      )}
    </div>
  );
}
