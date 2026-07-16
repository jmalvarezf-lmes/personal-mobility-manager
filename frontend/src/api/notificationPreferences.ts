export interface NotificationConfigFieldSchema {
  type: string;
  min?: number;
}

export interface NotificationType {
  key: string;
  label: string;
  config_schema: Record<string, NotificationConfigFieldSchema>;
}

export interface NotificationPreference {
  type_key: string;
  enabled: boolean;
  config: Record<string, number | string | boolean>;
}

export interface UpdateNotificationPreferenceRequest {
  enabled: boolean;
  config: Record<string, number | string | boolean>;
}

export async function getNotificationTypes(): Promise<NotificationType[]> {
  const response = await fetch("/api/notifications/types", { credentials: "include" });
  if (!response.ok) {
    throw new Error(`Failed to get notification types: ${response.status}`);
  }
  return (await response.json()) as NotificationType[];
}

export async function getNotificationPreferences(): Promise<NotificationPreference[]> {
  const response = await fetch("/api/notifications/preferences", { credentials: "include" });
  if (!response.ok) {
    throw new Error(`Failed to get notification preferences: ${response.status}`);
  }
  return (await response.json()) as NotificationPreference[];
}

export async function updateNotificationPreference(
  typeKey: string,
  payload: UpdateNotificationPreferenceRequest,
): Promise<NotificationPreference> {
  const response = await fetch(`/api/notifications/preferences/${typeKey}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Failed to update notification preference: ${response.status}`);
  }
  return (await response.json()) as NotificationPreference;
}
