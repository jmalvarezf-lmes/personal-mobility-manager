export interface UserPreferences {
  default_ticket_duration_minutes: number;
  auto_create_ticket: boolean;
  preferred_notification_channel: string | null;
  notification_language: string | null;
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
    throw new Error(text || `Failed to update preferences: ${response.status}`);
  }
  return (await response.json()) as UserPreferences;
}
