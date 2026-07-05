export interface SerTicketProviderConnections {
  providers: string[];
}

export interface ConnectSerTicketProviderPayload {
  provider: string;
  email: string;
  password: string;
}

export interface DisconnectSerTicketProviderResult {
  logout_succeeded: boolean;
}

export async function getConnections(): Promise<SerTicketProviderConnections> {
  const response = await fetch("/api/ser-ticket-providers/connections", {
    credentials: "include",
  });
  if (!response.ok) {
    throw new Error(`Failed to get connections: ${response.status}`);
  }
  return (await response.json()) as SerTicketProviderConnections;
}

export async function connect(payload: ConnectSerTicketProviderPayload): Promise<void> {
  const response = await fetch("/api/ser-ticket-providers/connections", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Failed to connect provider: ${response.status}`);
  }
}

export async function disconnect(
  provider: string,
): Promise<DisconnectSerTicketProviderResult> {
  const response = await fetch(`/api/ser-ticket-providers/connections/${provider}`, {
    method: "DELETE",
    credentials: "include",
  });
  if (!response.ok) {
    throw new Error(`Failed to disconnect provider: ${response.status}`);
  }
  return (await response.json()) as DisconnectSerTicketProviderResult;
}
