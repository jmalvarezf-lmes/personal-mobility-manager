import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { getAvailableLanguages, getConfiguredChannels } from "../api/notifications";
import {
  getNotificationPreferences,
  getNotificationTypes,
  updateNotificationPreference,
  type NotificationPreference,
  type NotificationType,
} from "../api/notificationPreferences";
import { getPreferences, updatePreferences } from "../api/preferences";
import Nav from "../components/Nav";

type NotificationPrefValue = {
  enabled: boolean;
  config: Record<string, number>;
};

type NotificationPrefState = Record<string, NotificationPrefValue>;

function toPrefState(prefs: NotificationPreference[]): NotificationPrefState {
  const state: NotificationPrefState = {};
  for (const pref of prefs) {
    state[pref.type_key] = {
      enabled: pref.enabled,
      config: pref.config as Record<string, number>,
    };
  }
  return state;
}

function prefsEqual(a: NotificationPrefValue, b: NotificationPrefValue): boolean {
  return a.enabled === b.enabled && JSON.stringify(a.config) === JSON.stringify(b.config);
}

export default function PreferencesPage() {
  const { t } = useTranslation();
  const [durationMinutes, setDurationMinutes] = useState(60);
  const [autoCreateTicket, setAutoCreateTicket] = useState(false);
  const [preferredChannel, setPreferredChannel] = useState<string | null>(null);
  const [notificationLanguage, setNotificationLanguage] = useState<string | null>(null);
  const [connectedChannels, setConnectedChannels] = useState<string[]>([]);
  const [availableLanguages, setAvailableLanguages] = useState<string[]>([]);
  const [notificationTypes, setNotificationTypes] = useState<NotificationType[]>([]);
  const [notificationPrefs, setNotificationPrefs] = useState<NotificationPrefState>({});
  const [notificationPrefsBaseline, setNotificationPrefsBaseline] = useState<NotificationPrefState>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    async function load() {
      try {
        const [prefs, channels, languages, types, notifPrefs] = await Promise.all([
          getPreferences(),
          getConfiguredChannels(),
          getAvailableLanguages(),
          getNotificationTypes(),
          getNotificationPreferences(),
        ]);
        setDurationMinutes(prefs.default_ticket_duration_minutes);
        setAutoCreateTicket(prefs.auto_create_ticket);
        setPreferredChannel(prefs.preferred_notification_channel);
        setNotificationLanguage(prefs.notification_language);
        setConnectedChannels(channels.channels);
        setAvailableLanguages(languages.languages);
        setNotificationTypes(types);
        const initialPrefs = toPrefState(notifPrefs);
        setNotificationPrefs(initialPrefs);
        setNotificationPrefsBaseline(initialPrefs);
      } catch (err) {
        setError(err instanceof Error ? err.message : t("page.preferences.loadError"));
      } finally {
        setLoading(false);
      }
    }
    void load();
  }, [t]);

  function handleNotificationToggle(typeKey: string, enabled: boolean) {
    setNotificationPrefs((prev) => ({
      ...prev,
      [typeKey]: { enabled, config: prev[typeKey]?.config ?? {} },
    }));
  }

  function handleNotificationConfigChange(typeKey: string, field: string, value: number) {
    setNotificationPrefs((prev) => ({
      ...prev,
      [typeKey]: {
        enabled: prev[typeKey]?.enabled ?? false,
        config: { ...prev[typeKey]?.config, [field]: value },
      },
    }));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSaved(false);

    if (durationMinutes <= 0) {
      setError(t("page.preferences.invalidDuration"));
      return;
    }

    for (const type of notificationTypes) {
      const pref = notificationPrefs[type.key];
      if (!pref?.enabled) continue;
      for (const [field, fieldSchema] of Object.entries(type.config_schema)) {
        const value = pref.config[field];
        if (
          fieldSchema.type === "integer" &&
          fieldSchema.min !== undefined &&
          typeof value === "number" &&
          value < fieldSchema.min
        ) {
          setError(t("page.preferences.notifications.invalidThreshold", { min: fieldSchema.min }));
          return;
        }
      }
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

      const changedTypeKeys = notificationTypes
        .map((type) => type.key)
        .filter((key) => {
          const current = notificationPrefs[key];
          if (!current) return false;
          const baseline = notificationPrefsBaseline[key];
          return !baseline || !prefsEqual(current, baseline);
        });

      if (changedTypeKeys.length > 0) {
        const updatedEntries = await Promise.all(
          changedTypeKeys.map(async (key) => {
            const current = notificationPrefs[key];
            const updatedPref = await updateNotificationPreference(key, {
              enabled: current.enabled,
              config: current.config,
            });
            return [key, updatedPref] as const;
          }),
        );
        setNotificationPrefs((prev) => {
          const next = { ...prev };
          for (const [key, updatedPref] of updatedEntries) {
            next[key] = { enabled: updatedPref.enabled, config: updatedPref.config as Record<string, number> };
          }
          return next;
        });
        setNotificationPrefsBaseline((prev) => {
          const next = { ...prev };
          for (const [key, updatedPref] of updatedEntries) {
            next[key] = { enabled: updatedPref.enabled, config: updatedPref.config as Record<string, number> };
          }
          return next;
        });
      }

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
              {availableLanguages.map((language) => (
                <option key={language} value={language}>
                  {t(`page.preferences.languages.${language}`)}
                </option>
              ))}
            </select>
          </div>

          {notificationTypes.length > 0 && (
            <div className="space-y-3 border-t border-gray-200 pt-4">
              <h2 className="text-sm font-semibold text-gray-800">
                {t("page.preferences.notifications.title")}
              </h2>
              {notificationTypes.map((type) => {
                const pref = notificationPrefs[type.key] ?? { enabled: false, config: {} };
                return (
                  <div key={type.key} className="space-y-2 rounded border border-gray-200 p-3">
                    <div className="flex items-center gap-2">
                      <input
                        id={`notification-${type.key}-enabled`}
                        type="checkbox"
                        checked={pref.enabled}
                        onChange={(e) => handleNotificationToggle(type.key, e.target.checked)}
                        className="h-4 w-4 rounded border-gray-300"
                      />
                      <label
                        className="text-sm font-medium text-gray-700"
                        htmlFor={`notification-${type.key}-enabled`}
                      >
                        {t(`page.preferences.notifications.typeLabels.${type.key}`, {
                          defaultValue: type.label,
                        })}
                      </label>
                    </div>

                    {pref.enabled &&
                      Object.keys(type.config_schema).map((field) => (
                        <div key={field} className="pl-6">
                          <label
                            className="mb-1 block text-sm font-medium text-gray-700"
                            htmlFor={`notification-${type.key}-${field}`}
                          >
                            {t(`page.preferences.notifications.fields.${field}.label`, {
                              defaultValue: field,
                            })}
                          </label>
                          <input
                            id={`notification-${type.key}-${field}`}
                            type="number"
                            min={type.config_schema[field]?.min}
                            value={pref.config[field] ?? ""}
                            onChange={(e) =>
                              handleNotificationConfigChange(type.key, field, Number(e.target.value))
                            }
                            className="w-full max-w-[10rem] rounded border border-gray-300 px-3 py-2 text-sm"
                          />
                          <p className="mt-1 text-xs text-gray-500">
                            {t(`page.preferences.notifications.fields.${field}.help`, {
                              defaultValue: "",
                            })}
                          </p>
                        </div>
                      ))}
                  </div>
                );
              })}
            </div>
          )}

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
