import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  getNotificationPreferences,
  getNotificationTypes,
  updateNotificationPreference,
} from "./notificationPreferences";

function jsonResponse(body: unknown, init: ResponseInit = {}): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
    ...init,
  });
}

describe("notificationPreferences api", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  describe("getNotificationTypes", () => {
    it("requests notification types with credentials", async () => {
      const types = [{ key: "ticket_reminder", label: "Ticket reminder", config_schema: {} }];
      vi.mocked(fetch).mockResolvedValue(jsonResponse(types));

      const result = await getNotificationTypes();

      expect(fetch).toHaveBeenCalledWith("/api/notifications/types", {
        credentials: "include",
      });
      expect(result).toEqual(types);
    });

    it("throws on a non-OK response", async () => {
      vi.mocked(fetch).mockResolvedValue(new Response(null, { status: 500 }));

      await expect(getNotificationTypes()).rejects.toThrow(
        "Failed to get notification types: 500",
      );
    });
  });

  describe("getNotificationPreferences", () => {
    it("requests notification preferences with credentials", async () => {
      const prefs = [{ type_key: "ticket_reminder", enabled: true, config: {} }];
      vi.mocked(fetch).mockResolvedValue(jsonResponse(prefs));

      const result = await getNotificationPreferences();

      expect(fetch).toHaveBeenCalledWith("/api/notifications/preferences", {
        credentials: "include",
      });
      expect(result).toEqual(prefs);
    });

    it("throws on a non-OK response", async () => {
      vi.mocked(fetch).mockResolvedValue(new Response(null, { status: 500 }));

      await expect(getNotificationPreferences()).rejects.toThrow(
        "Failed to get notification preferences: 500",
      );
    });
  });

  describe("updateNotificationPreference", () => {
    it("PUTs the JSON-serialized payload to the type-scoped URL", async () => {
      const payload = { enabled: false, config: { minutes: 10 } };
      const updated = { type_key: "ticket_reminder", ...payload };
      vi.mocked(fetch).mockResolvedValue(jsonResponse(updated));

      const result = await updateNotificationPreference("ticket_reminder", payload);

      expect(fetch).toHaveBeenCalledWith(
        "/api/notifications/preferences/ticket_reminder",
        {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          credentials: "include",
          body: JSON.stringify(payload),
        },
      );
      expect(result).toEqual(updated);
    });

    it("throws an Error whose message includes the response body text", async () => {
      vi.mocked(fetch).mockResolvedValue(
        new Response("Invalid config", { status: 422 }),
      );

      await expect(
        updateNotificationPreference("ticket_reminder", { enabled: true, config: {} }),
      ).rejects.toThrow("Invalid config");
    });

    it("falls back to a generic message when the response body is empty", async () => {
      vi.mocked(fetch).mockResolvedValue(new Response("", { status: 500 }));

      await expect(
        updateNotificationPreference("ticket_reminder", { enabled: true, config: {} }),
      ).rejects.toThrow("Failed to update notification preference: 500");
    });
  });
});
