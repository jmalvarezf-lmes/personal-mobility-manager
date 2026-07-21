import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { getPreferences, updatePreferences, type UserPreferences } from "./preferences";

function jsonResponse(body: unknown, init: ResponseInit = {}): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
    ...init,
  });
}

describe("preferences api", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  describe("getPreferences", () => {
    it("requests preferences with credentials", async () => {
      const prefs: UserPreferences = {
        default_ticket_duration_minutes: 60,
        auto_create_ticket: true,
        preferred_notification_channel: "telegram",
        notification_language: "en",
        timezone: "Europe/Madrid",
      };
      vi.mocked(fetch).mockResolvedValue(jsonResponse(prefs));

      const result = await getPreferences();

      expect(fetch).toHaveBeenCalledWith("/api/preferences", {
        credentials: "include",
      });
      expect(result).toEqual(prefs);
    });

    it("throws on a non-OK response", async () => {
      vi.mocked(fetch).mockResolvedValue(new Response(null, { status: 500 }));

      await expect(getPreferences()).rejects.toThrow(
        "Failed to get preferences: 500",
      );
    });
  });

  describe("updatePreferences", () => {
    const payload: UserPreferences = {
      default_ticket_duration_minutes: 30,
      auto_create_ticket: false,
      preferred_notification_channel: null,
      notification_language: null,
      timezone: null,
    };

    it("PUTs the JSON-serialized payload", async () => {
      vi.mocked(fetch).mockResolvedValue(jsonResponse(payload));

      const result = await updatePreferences(payload);

      expect(fetch).toHaveBeenCalledWith("/api/preferences", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify(payload),
      });
      expect(result).toEqual(payload);
    });

    it("throws an Error whose message includes the response body text", async () => {
      vi.mocked(fetch).mockResolvedValue(
        new Response("Invalid timezone", { status: 422 }),
      );

      await expect(updatePreferences(payload)).rejects.toThrow(
        "Invalid timezone",
      );
    });

    it("falls back to a generic message when the response body is empty", async () => {
      vi.mocked(fetch).mockResolvedValue(new Response("", { status: 500 }));

      await expect(updatePreferences(payload)).rejects.toThrow(
        "Failed to update preferences: 500",
      );
    });
  });
});
