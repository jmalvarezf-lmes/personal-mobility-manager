export interface UserPreferences {
  default_ticket_duration_minutes: number;
  auto_create_ticket: boolean;
  preferred_notification_channel: string | null;
  notification_language: string | null;
  timezone: string | null;
}

/**
 * Thrown by updatePreferences() on a non-2xx response. `code` is set when the
 * backend returned a structured `{"error_code": "...", "message": "..."}`
 * detail (e.g. FastAPI's ser_provider_not_connected rejection) — callers can
 * use it to look up a localized message, falling back to `message` (English,
 * from the backend) when no `code` is present or no translation exists.
 */
export class PreferencesUpdateError extends Error {
  code?: string;

  constructor(message: string, code?: string) {
    super(message);
    this.code = code;
  }
}

export async function getPreferences(): Promise<UserPreferences> {
  const response = await fetch("/api/preferences", { credentials: "include" });
  if (!response.ok) {
    throw new Error(`Failed to get preferences: ${response.status}`);
  }
  return (await response.json()) as UserPreferences;
}

export async function updatePreferences(
  payload: UserPreferences,
): Promise<UserPreferences> {
  const response = await fetch("/api/preferences", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const text = await response.text();
    // FastAPI's HTTPException body is `{"detail": "..."}` for a plain string
    // detail, or `{"detail": {"error_code": "...", "message": "..."}}` for
    // the structured rejections this endpoint also returns (e.g. the
    // "connect a provider first" case) — surface a clean message (and the
    // error_code, when present) rather than the raw JSON text.
    let code: string | undefined;
    let detail: string | null = null;
    try {
      const parsed = JSON.parse(text) as { detail?: unknown };
      if (typeof parsed.detail === "string") {
        detail = parsed.detail;
      } else if (parsed.detail && typeof parsed.detail === "object") {
        const structured = parsed.detail as { error_code?: unknown; message?: unknown };
        if (typeof structured.error_code === "string") code = structured.error_code;
        if (typeof structured.message === "string") detail = structured.message;
      }
    } catch {
      // Not JSON — fall through to the raw text/status fallback below.
    }
    throw new PreferencesUpdateError(detail ?? (text || `Failed to update preferences: ${response.status}`), code);
  }
  return (await response.json()) as UserPreferences;
}
