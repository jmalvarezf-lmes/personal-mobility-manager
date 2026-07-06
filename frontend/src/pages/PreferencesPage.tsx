import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { getConfiguredChannels } from "../api/notifications";
import { getPreferences, updatePreferences } from "../api/preferences";
import Nav from "../components/Nav";

const SUPPORTED_LANGUAGES = ["en", "es"];

export default function PreferencesPage() {
  const { t } = useTranslation();
  const [durationMinutes, setDurationMinutes] = useState(60);
  const [autoCreateTicket, setAutoCreateTicket] = useState(false);
  const [preferredChannel, setPreferredChannel] = useState<string | null>(null);
  const [notificationLanguage, setNotificationLanguage] = useState<string | null>(null);
  const [connectedChannels, setConnectedChannels] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    async function load() {
      try {
        const [prefs, channels] = await Promise.all([getPreferences(), getConfiguredChannels()]);
        setDurationMinutes(prefs.default_ticket_duration_minutes);
        setAutoCreateTicket(prefs.auto_create_ticket);
        setPreferredChannel(prefs.preferred_notification_channel);
        setNotificationLanguage(prefs.notification_language);
        setConnectedChannels(channels.channels);
      } catch (err) {
        setError(err instanceof Error ? err.message : t("page.preferences.loadError"));
      } finally {
        setLoading(false);
      }
    }
    void load();
  }, [t]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSaved(false);

    if (durationMinutes <= 0) {
      setError(t("page.preferences.invalidDuration"));
      return;
    }

    setSaving(true);
    try {
      const updated = await updatePreferences({
        default_ticket_duration_minutes: durationMinutes,
        auto_create_ticket: autoCreateTicket,
        preferred_notification_channel: preferredChannel,
        notification_language: notificationLanguage,
      });
      setDurationMinutes(updated.default_ticket_duration_minutes);
      setAutoCreateTicket(updated.auto_create_ticket);
      setPreferredChannel(updated.preferred_notification_channel);
      setNotificationLanguage(updated.notification_language);
      setSaved(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : t("page.preferences.saveError"));
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center text-gray-600">
        {t("page.preferences.loading")}
      </div>
    );
  }

  return (
    <div className="flex h-screen flex-col">
      <Nav />
      <div className="flex-1 overflow-auto p-6">
        <h1 className="mb-4 text-2xl font-bold text-gray-800">
          {t("page.preferences.title")}
        </h1>

        <form
          onSubmit={(e) => void handleSubmit(e)}
          noValidate
          className="max-w-md space-y-4"
        >
          <div>
            <label
              className="mb-1 block text-sm font-medium text-gray-700"
              htmlFor="default-ticket-duration"
            >
              {t("page.preferences.durationLabel")}
            </label>
            <input
              id="default-ticket-duration"
              type="number"
              min={1}
              value={durationMinutes}
              onChange={(e) => setDurationMinutes(Number(e.target.value))}
              className="w-full rounded border border-gray-300 px-3 py-2 text-sm"
            />
          </div>

          <div className="flex items-center gap-2">
            <input
              id="auto-create-ticket"
              type="checkbox"
              checked={autoCreateTicket}
              onChange={(e) => setAutoCreateTicket(e.target.checked)}
              className="h-4 w-4 rounded border-gray-300"
            />
            <label
              className="text-sm font-medium text-gray-700"
              htmlFor="auto-create-ticket"
            >
              {t("page.preferences.autoCreateLabel")}
            </label>
          </div>

          <div>
            <label
              className="mb-1 block text-sm font-medium text-gray-700"
              htmlFor="preferred-notification-channel"
            >
              {t("page.preferences.preferredChannelLabel")}
            </label>
            {connectedChannels.length === 0 ? (
              <p className="text-sm text-gray-500">
                {t("page.preferences.noChannelsConnected")}
              </p>
            ) : (
              <select
                id="preferred-notification-channel"
                value={preferredChannel ?? ""}
                onChange={(e) => setPreferredChannel(e.target.value || null)}
                className="w-full rounded border border-gray-300 px-3 py-2 text-sm"
              >
                <option value="">{t("page.preferences.noPreferredChannel")}</option>
                {connectedChannels.map((channel) => (
                  <option key={channel} value={channel}>
                    {t(`page.notificationChannels.channels.${channel}`, { defaultValue: channel })}
                  </option>
                ))}
              </select>
            )}
          </div>

          <div>
            <label
              className="mb-1 block text-sm font-medium text-gray-700"
              htmlFor="notification-language"
            >
              {t("page.preferences.notificationLanguageLabel")}
            </label>
            <select
              id="notification-language"
              value={notificationLanguage ?? ""}
              onChange={(e) => setNotificationLanguage(e.target.value || null)}
              className="w-full rounded border border-gray-300 px-3 py-2 text-sm"
            >
              <option value="">{t("page.preferences.noNotificationLanguage")}</option>
              {SUPPORTED_LANGUAGES.map((language) => (
                <option key={language} value={language}>
                  {t(`page.preferences.languages.${language}`)}
                </option>
              ))}
            </select>
          </div>

          {error && (
            <p role="alert" className="text-sm text-red-600">
              {error}
            </p>
          )}

          {saved && !error && (
            <p className="text-sm text-green-600">
              {t("page.preferences.saved")}
            </p>
          )}

          <div className="flex justify-end pt-2">
            <button
              type="submit"
              disabled={saving}
              className="rounded bg-blue-600 px-4 py-2 text-sm text-white hover:bg-blue-700 disabled:opacity-50"
            >
              {saving ? t("page.preferences.saving") : t("page.preferences.save")}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
