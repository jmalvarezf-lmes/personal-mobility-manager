import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { connect, disconnect, getConnections } from "./serTicketProviders";

function jsonResponse(body: unknown, init: ResponseInit = {}): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
    ...init,
  });
}

describe("serTicketProviders api", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  describe("getConnections", () => {
    it("requests connections with credentials", async () => {
      const body = { providers: ["ser"] };
      vi.mocked(fetch).mockResolvedValue(jsonResponse(body));

      const result = await getConnections();

      expect(fetch).toHaveBeenCalledWith("/api/ser-ticket-providers/connections", {
        credentials: "include",
      });
      expect(result).toEqual(body);
    });

    it("throws on a non-OK response", async () => {
      vi.mocked(fetch).mockResolvedValue(new Response(null, { status: 500 }));

      await expect(getConnections()).rejects.toThrow(
        "Failed to get connections: 500",
      );
    });
  });

  describe("connect", () => {
    const payload = { provider: "ser", email: "a@b.com", password: "secret" };

    it("POSTs the JSON-serialized payload", async () => {
      vi.mocked(fetch).mockResolvedValue(new Response(null, { status: 204 }));

      await connect(payload);

      expect(fetch).toHaveBeenCalledWith("/api/ser-ticket-providers/connections", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify(payload),
      });
    });

    it("throws an Error whose message includes the response body text", async () => {
      vi.mocked(fetch).mockResolvedValue(
        new Response("Invalid credentials", { status: 401 }),
      );

      await expect(connect(payload)).rejects.toThrow("Invalid credentials");
    });

    it("falls back to a generic message when the response body is empty", async () => {
      vi.mocked(fetch).mockResolvedValue(new Response("", { status: 500 }));

      await expect(connect(payload)).rejects.toThrow(
        "Failed to connect provider: 500",
      );
    });
  });

  describe("disconnect", () => {
    it("DELETEs the provider-scoped URL", async () => {
      const body = { logout_succeeded: true };
      vi.mocked(fetch).mockResolvedValue(jsonResponse(body));

      const result = await disconnect("ser");

      expect(fetch).toHaveBeenCalledWith("/api/ser-ticket-providers/connections/ser", {
        method: "DELETE",
        credentials: "include",
      });
      expect(result).toEqual(body);
    });

    it("throws on a non-OK response", async () => {
      vi.mocked(fetch).mockResolvedValue(new Response(null, { status: 500 }));

      await expect(disconnect("ser")).rejects.toThrow(
        "Failed to disconnect provider: 500",
      );
    });
  });
});
