import { useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { getAvailableLanguages, getConfiguredChannels } from "../api/notifications";
import {
  getNotificationPreferences,
  getNotificationTypes,
  updateNotificationPreference,
  type NotificationPreference,
  type NotificationType,
} from "../api/notificationPreferences";
import { getPreferences, PreferencesUpdateError, updatePreferences } from "../api/preferences";
import Nav from "../components/Nav";
import { listTimezoneOptions, type TimezoneOption } from "../utils/timezone";

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

/** The combobox's display text for a committed timezone value: its option label, or "" if unset/unmatched. */
function labelForTimezone(value: string | null, options: TimezoneOption[]): string {
  if (!value) return "";
  return options.find((option) => option.value === value)?.label ?? "";
}

// Notification types whose enabled state is mutually exclusive with the
// in-progress (not-yet-saved) auto_create_ticket value — see the
// notification-type-preferences spec's lock table. `ser_zone_ticket_required`
// is locked while auto_create_ticket is checked; the two new SER-ticket
// event types are locked while it is unchecked.
const _LOCKED_WHEN_AUTO_CREATE_TICKET_IS: Record<string, boolean> = {
  ser_zone_ticket_required: true,
  ser_ticket_created: false,
  ser_ticket_creation_failed: false,
};

function isLockedByAutoCreateTicket(typeKey: string, autoCreateTicket: boolean): boolean {
  return _LOCKED_WHEN_AUTO_CREATE_TICKET_IS[typeKey] === autoCreateTicket;
}

export default function PreferencesPage() {
  const { t } = useTranslation();
  const [durationMinutes, setDurationMinutes] = useState(60);
  const [autoCreateTicket, setAutoCreateTicket] = useState(false);
  const [preferredChannel, setPreferredChannel] = useState<string | null>(null);
  const [notificationLanguage, setNotificationLanguage] = useState<string | null>(null);
  const [timezone, setTimezone] = useState<string | null>(null);
  // Holds whatever text the combobox input currently displays: either the
  // label of the committed `timezone` value (when the dropdown isn't
  // actively open for searching), or in-progress typed search text.
  const [timezoneSearch, setTimezoneSearch] = useState("");
  const [isTimezoneDropdownOpen, setIsTimezoneDropdownOpen] = useState(false);
  const timezoneBlurTimeout = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [connectedChannels, setConnectedChannels] = useState<string[]>([]);
  const [availableLanguages, setAvailableLanguages] = useState<string[]>([]);
  // Computed once on mount — the picker's abbreviation labels are evaluated
  // against today's date, which doesn't need to change per keystroke or
  // per render (see design.md Decision 3).
  const [timezoneOptions] = useState<TimezoneOption[]>(() => listTimezoneOptions());
  const [notificationTypes, setNotificationTypes] = useState<NotificationType[]>([]);
  const [notificationPrefs, setNotificationPrefs] = useState<NotificationPrefState>({});
  const [notificationPrefsBaseline, setNotificationPrefsBaseline] = useState<NotificationPrefState>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  // The blur handler below defers closing the combobox by a short delay so a
  // click on a dropdown option can register first; clear that timer on
  // unmount so it never fires setState after the component is gone.
  useEffect(() => {
    return () => {
      if (timezoneBlurTimeout.current) clearTimeout(timezoneBlurTimeout.current);
    };
  }, []);

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
        setTimezone(prefs.timezone);
        setTimezoneSearch(labelForTimezone(prefs.timezone, timezoneOptions));
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
  }, [t, timezoneOptions]);

  // Filter-as-you-type over the full IANA zone list. The currently selected
  // zone is always kept in the option list (even if it no longer matches
  // the search term) so the combobox's committed value stays valid.
  const filteredTimezoneOptions = useMemo(() => {
    const term = timezoneSearch.trim().toLowerCase();
    const base = term
      ? timezoneOptions.filter((option) => option.value.toLowerCase().includes(term))
      : timezoneOptions;
    if (timezone && !base.some((option) => option.value === timezone)) {
      const current = timezoneOptions.find((option) => option.value === timezone);
      if (current) return [current, ...base];
    }
    return base;
  }, [timezoneSearch, timezone, timezoneOptions]);

  function selectTimezoneOption(option: TimezoneOption) {
    setTimezone(option.value);
    setTimezoneSearch(option.label);
    setIsTimezoneDropdownOpen(false);
  }

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
        timezone,
      });
      setDurationMinutes(updated.default_ticket_duration_minutes);
      setAutoCreateTicket(updated.auto_create_ticket);
      setPreferredChannel(updated.preferred_notification_channel);
      setNotificationLanguage(updated.notification_language);
      setTimezone(updated.timezone);

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
      if (err instanceof PreferencesUpdateError && err.code) {
        setError(t(`page.preferences.errors.${err.code}`, { defaultValue: err.message }));
      } else {
        setError(err instanceof Error ? err.message : t("page.preferences.saveError"));
      }
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

          <div>
            <label
              className="mb-1 block text-sm font-medium text-gray-700"
              htmlFor="timezone-search"
            >
              {t("page.preferences.timezoneLabel")}
            </label>
            <div className="flex gap-2">
              <div className="relative w-full">
                <input
                  id="timezone-search"
                  type="text"
                  role="combobox"
                  aria-expanded={isTimezoneDropdownOpen}
                  aria-autocomplete="list"
                  aria-controls="timezone-listbox"
                  autoComplete="off"
                  value={timezoneSearch}
                  onChange={(e) => {
                    setTimezoneSearch(e.target.value);
                    setIsTimezoneDropdownOpen(true);
                  }}
                  onFocus={(e) => {
                    if (timezoneBlurTimeout.current) {
                      clearTimeout(timezoneBlurTimeout.current);
                      timezoneBlurTimeout.current = null;
                    }
                    setIsTimezoneDropdownOpen(true);
                    e.target.select();
                  }}
                  onBlur={() => {
                    timezoneBlurTimeout.current = setTimeout(() => {
                      setIsTimezoneDropdownOpen(false);
                      setTimezoneSearch(labelForTimezone(timezone, timezoneOptions));
                    }, 150);
                  }}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      e.preventDefault();
                      if (isTimezoneDropdownOpen && filteredTimezoneOptions.length > 0) {
                        selectTimezoneOption(filteredTimezoneOptions[0]);
                      }
                    } else if (e.key === "Escape") {
                      setIsTimezoneDropdownOpen(false);
                    }
                  }}
                  placeholder={t("page.preferences.timezoneSearchPlaceholder")}
                  className="w-full rounded border border-gray-300 px-3 py-2 text-sm"
                />
                {isTimezoneDropdownOpen && (
                  <ul
                    id="timezone-listbox"
                    role="listbox"
                    className="absolute z-10 mt-1 max-h-56 w-full overflow-auto rounded border border-gray-300 bg-white shadow-md"
                  >
                    {filteredTimezoneOptions.length === 0 ? (
                      <li className="px-3 py-2 text-sm text-gray-500">
                        {t("page.preferences.noTimezoneMatches")}
                      </li>
                    ) : (
                      filteredTimezoneOptions.map((option) => (
                        <li
                          key={option.value}
                          role="option"
                          aria-selected={option.value === timezone}
                        >
                          <button
                            type="button"
                            onMouseDown={(e) => e.preventDefault()}
                            onClick={() => selectTimezoneOption(option)}
                            className="block w-full px-3 py-2 text-left text-sm hover:bg-gray-100"
                          >
                            {option.label}
                          </button>
                        </li>
                      ))
                    )}
                  </ul>
                )}
              </div>
              {timezone && (
                <button
                  type="button"
                  onClick={() => {
                    setTimezone(null);
                    setTimezoneSearch("");
                    setIsTimezoneDropdownOpen(false);
                  }}
                  className="rounded bg-gray-100 px-3 py-2 text-sm hover:bg-gray-200"
                >
                  {t("page.preferences.clearTimezone")}
                </button>
              )}
            </div>
          </div>

          {notificationTypes.length > 0 && (
            <div className="space-y-3 border-t border-gray-200 pt-4">
              <h2 className="text-sm font-semibold text-gray-800">
                {t("page.preferences.notifications.title")}
              </h2>
              {notificationTypes.map((type) => {
                const pref = notificationPrefs[type.key] ?? { enabled: false, config: {} };
                const locked = isLockedByAutoCreateTicket(type.key, autoCreateTicket);
                return (
                  <div key={type.key} className="space-y-2 rounded border border-gray-200 p-3">
                    <div className="flex items-center gap-2">
                      <input
                        id={`notification-${type.key}-enabled`}
                        type="checkbox"
                        checked={pref.enabled}
                        disabled={locked}
                        onChange={(e) => handleNotificationToggle(type.key, e.target.checked)}
                        className="h-4 w-4 rounded border-gray-300 disabled:cursor-not-allowed disabled:opacity-50"
                      />
                      <label
                        className={`text-sm font-medium ${locked ? "text-gray-400" : "text-gray-700"}`}
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
