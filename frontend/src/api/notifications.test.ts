import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  createTelegramLinkCode,
  disconnectChannel,
  getAvailableChannels,
  getAvailableLanguages,
  getConfiguredChannels,
} from "./notifications";

function jsonResponse(body: unknown, init: ResponseInit = {}): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
    ...init,
  });
}

describe("notifications api", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  describe("getAvailableChannels", () => {
    it("requests available channels with credentials", async () => {
      const body = { channels: ["telegram"] };
      vi.mocked(fetch).mockResolvedValue(jsonResponse(body));

      const result = await getAvailableChannels();

      expect(fetch).toHaveBeenCalledWith("/api/notifications/available-channels", {
        credentials: "include",
      });
      expect(result).toEqual(body);
    });

    it("throws on a non-OK response", async () => {
      vi.mocked(fetch).mockResolvedValue(new Response(null, { status: 500 }));

      await expect(getAvailableChannels()).rejects.toThrow(
        "Failed to get available channels: 500",
      );
    });
  });

  describe("getAvailableLanguages", () => {
    it("requests available languages with credentials", async () => {
      const body = { languages: ["en", "es"] };
      vi.mocked(fetch).mockResolvedValue(jsonResponse(body));

      const result = await getAvailableLanguages();

      expect(fetch).toHaveBeenCalledWith("/api/notifications/languages", {
        credentials: "include",
      });
      expect(result).toEqual(body);
    });

    it("throws on a non-OK response", async () => {
      vi.mocked(fetch).mockResolvedValue(new Response(null, { status: 500 }));

      await expect(getAvailableLanguages()).rejects.toThrow(
        "Failed to get available languages: 500",
      );
    });
  });

  describe("getConfiguredChannels", () => {
    it("requests configured channels with credentials", async () => {
      const body = { channels: ["telegram"] };
      vi.mocked(fetch).mockResolvedValue(jsonResponse(body));

      const result = await getConfiguredChannels();

      expect(fetch).toHaveBeenCalledWith("/api/notifications/channels", {
        credentials: "include",
      });
      expect(result).toEqual(body);
    });

    it("throws on a non-OK response", async () => {
      vi.mocked(fetch).mockResolvedValue(new Response(null, { status: 500 }));

      await expect(getConfiguredChannels()).rejects.toThrow(
        "Failed to get configured channels: 500",
      );
    });
  });

  describe("disconnectChannel", () => {
    it("DELETEs the channel-scoped URL", async () => {
      vi.mocked(fetch).mockResolvedValue(new Response(null, { status: 204 }));

      await disconnectChannel("telegram");

      expect(fetch).toHaveBeenCalledWith("/api/notifications/channels/telegram", {
        method: "DELETE",
        credentials: "include",
      });
    });

    it("throws on a non-OK response", async () => {
      vi.mocked(fetch).mockResolvedValue(new Response(null, { status: 500 }));

      await expect(disconnectChannel("telegram")).rejects.toThrow(
        "Failed to disconnect channel: 500",
      );
    });
  });

  describe("createTelegramLinkCode", () => {
    it("POSTs to the link-code endpoint with credentials", async () => {
      const body = { deep_link: "https://t.me/bot?start=abc" };
      vi.mocked(fetch).mockResolvedValue(jsonResponse(body));

      const result = await createTelegramLinkCode();

      expect(fetch).toHaveBeenCalledWith("/api/notifications/telegram/link-code", {
        method: "POST",
        credentials: "include",
      });
      expect(result).toEqual(body);
    });

    it("throws an Error whose message includes the response body text", async () => {
      vi.mocked(fetch).mockResolvedValue(
        new Response("Telegram not configured", { status: 400 }),
      );

      await expect(createTelegramLinkCode()).rejects.toThrow(
        "Telegram not configured",
      );
    });

    it("falls back to a generic message when the response body is empty", async () => {
      vi.mocked(fetch).mockResolvedValue(new Response("", { status: 500 }));

      await expect(createTelegramLinkCode()).rejects.toThrow(
        "Failed to create Telegram link code: 500",
      );
    });
  });
});
