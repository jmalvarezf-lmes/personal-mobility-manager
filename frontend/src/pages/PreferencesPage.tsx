import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { getPreferences, updatePreferences } from "../api/preferences";
import Nav from "../components/Nav";

export default function PreferencesPage() {
  const { t } = useTranslation();
  const [durationMinutes, setDurationMinutes] = useState(60);
  const [autoCreateTicket, setAutoCreateTicket] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    async function load() {
      try {
        const prefs = await getPreferences();
        setDurationMinutes(prefs.default_ticket_duration_minutes);
        setAutoCreateTicket(prefs.auto_create_ticket);
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
      });
      setDurationMinutes(updated.default_ticket_duration_minutes);
      setAutoCreateTicket(updated.auto_create_ticket);
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
