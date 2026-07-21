import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { getMe, logout } from "./auth";

function jsonResponse(body: unknown, init: ResponseInit = {}): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
    ...init,
  });
}

describe("auth api", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  describe("getMe", () => {
    it("requests the current user with credentials", async () => {
      const user = { id: "1", email: "a@b.com", display_name: "A" };
      vi.mocked(fetch).mockResolvedValue(jsonResponse(user));

      const result = await getMe();

      expect(fetch).toHaveBeenCalledWith("/api/auth/me", {
        credentials: "include",
      });
      expect(result).toEqual(user);
    });

    it("returns null on a 401 response", async () => {
      vi.mocked(fetch).mockResolvedValue(new Response(null, { status: 401 }));

      await expect(getMe()).resolves.toBeNull();
    });

    it("throws on any other non-OK response", async () => {
      vi.mocked(fetch).mockResolvedValue(new Response(null, { status: 500 }));

      await expect(getMe()).rejects.toThrow(
        "Unexpected response from /auth/me: 500",
      );
    });
  });

  describe("logout", () => {
    it("POSTs to the logout endpoint with credentials", async () => {
      vi.mocked(fetch).mockResolvedValue(new Response(null, { status: 204 }));

      await logout();

      expect(fetch).toHaveBeenCalledWith("/api/auth/logout", {
        method: "POST",
        credentials: "include",
      });
    });

    it("throws on a non-OK response", async () => {
      vi.mocked(fetch).mockResolvedValue(new Response(null, { status: 500 }));

      await expect(logout()).rejects.toThrow("Logout failed: 500");
    });
  });
});
