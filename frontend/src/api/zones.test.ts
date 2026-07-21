import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { fetchZoneOptions, fetchZones } from "./zones";

function jsonResponse(body: unknown, init: ResponseInit = {}): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
    ...init,
  });
}

describe("zones api", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  describe("fetchZones", () => {
    it("requests zones for the default city", async () => {
      const body = { zones: [{ id: "1" }], frontiers: [{ id: "f1" }] };
      vi.mocked(fetch).mockResolvedValue(jsonResponse(body));

      const result = await fetchZones();

      expect(fetch).toHaveBeenCalledWith("/api/parking/ser-zones?city=madrid");
      expect(result).toEqual({ zones: body.zones, frontiers: body.frontiers });
    });

    it("requests zones for an explicit city", async () => {
      vi.mocked(fetch).mockResolvedValue(jsonResponse({ zones: [], frontiers: [] }));

      await fetchZones("barcelona");

      expect(fetch).toHaveBeenCalledWith("/api/parking/ser-zones?city=barcelona");
    });

    it("throws on a non-OK response", async () => {
      vi.mocked(fetch).mockResolvedValue(new Response(null, { status: 500 }));

      await expect(fetchZones()).rejects.toThrow("Failed to fetch zones: 500");
    });
  });

  describe("fetchZoneOptions", () => {
    it("requests zone options with sort=asc for the given city", async () => {
      const options = [{ zone_number: "1", neighbourhood: "Centro" }];
      vi.mocked(fetch).mockResolvedValue(jsonResponse({ options }));

      const result = await fetchZoneOptions("madrid");

      expect(fetch).toHaveBeenCalledWith(
        "/api/parking/ser-zone-options?city=madrid&sort=asc",
      );
      expect(result).toEqual(options);
    });

    it("throws on a non-OK response", async () => {
      vi.mocked(fetch).mockResolvedValue(new Response(null, { status: 500 }));

      await expect(fetchZoneOptions("madrid")).rejects.toThrow(
        "Failed to fetch zone options: 500",
      );
    });
  });
});
