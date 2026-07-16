export interface NotificationChannelsResponse {
  channels: string[];
}

export interface NotificationLanguagesResponse {
  languages: string[];
}

export interface TelegramLinkCodeResponse {
  deep_link: string;
}

export async function getAvailableChannels(): Promise<NotificationChannelsResponse> {
  const response = await fetch("/api/notifications/available-channels", {
    credentials: "include",
  });
  if (!response.ok) {
    throw new Error(`Failed to get available channels: ${response.status}`);
  }
  return (await response.json()) as NotificationChannelsResponse;
}

export async function getAvailableLanguages(): Promise<NotificationLanguagesResponse> {
  const response = await fetch("/api/notifications/languages", {
    credentials: "include",
  });
  if (!response.ok) {
    throw new Error(`Failed to get available languages: ${response.status}`);
  }
  return (await response.json()) as NotificationLanguagesResponse;
}

export async function getConfiguredChannels(): Promise<NotificationChannelsResponse> {
  const response = await fetch("/api/notifications/channels", {
    credentials: "include",
  });
  if (!response.ok) {
    throw new Error(`Failed to get configured channels: ${response.status}`);
  }
  return (await response.json()) as NotificationChannelsResponse;
}

export async function disconnectChannel(channel: string): Promise<void> {
  const response = await fetch(`/api/notifications/channels/${channel}`, {
    method: "DELETE",
    credentials: "include",
  });
  if (!response.ok) {
    throw new Error(`Failed to disconnect channel: ${response.status}`);
  }
}

export async function createTelegramLinkCode(): Promise<TelegramLinkCodeResponse> {
  const response = await fetch("/api/notifications/telegram/link-code", {
    method: "POST",
    credentials: "include",
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Failed to create Telegram link code: ${response.status}`);
  }
  return (await response.json()) as TelegramLinkCodeResponse;
}
