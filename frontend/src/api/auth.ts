export interface User {
  id: string;
  email: string;
  display_name: string;
}

export async function getMe(): Promise<User | null> {
  const response = await fetch("/api/auth/me", { credentials: "include" });
  if (response.status === 401) {
    return null;
  }
  if (!response.ok) {
    throw new Error(`Unexpected response from /auth/me: ${response.status}`);
  }
  return (await response.json()) as User;
}

export async function logout(): Promise<void> {
  const response = await fetch("/api/auth/logout", {
    method: "POST",
    credentials: "include",
  });
  if (!response.ok) {
    throw new Error(`Logout failed: ${response.status}`);
  }
}
