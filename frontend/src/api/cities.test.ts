import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { listCities } from "./cities";

function jsonResponse(body: unknown, init: ResponseInit = {}): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
    ...init,
  });
}

describe("cities api", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  describe("listCities", () => {
    it("requests the city list", async () => {
      const cities = [{ code: "madrid", name: "Madrid" }];
      vi.mocked(fetch).mockResolvedValue(jsonResponse(cities));

      const result = await listCities();

      expect(fetch).toHaveBeenCalledWith("/api/cities");
      expect(result).toEqual(cities);
    });

    it("throws on a non-OK response", async () => {
      vi.mocked(fetch).mockResolvedValue(new Response(null, { status: 500 }));

      await expect(listCities()).rejects.toThrow("Failed to list cities: 500");
    });
  });
});
