import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  clearSerParkingExemption,
  createVehicle,
  deleteVehicle,
  getSerParkingExemption,
  getSerTicketHistory,
  getVehicle,
  getVehicleLocationHistory,
  listVehicles,
  setSerParkingExemption,
  updateVehicle,
} from "./vehicles";

function jsonResponse(body: unknown, init: ResponseInit = {}): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
    ...init,
  });
}

describe("vehicles api", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  describe("listVehicles", () => {
    it("requests the vehicle list with credentials", async () => {
      const vehicles = [{ id: "1" }];
      vi.mocked(fetch).mockResolvedValue(jsonResponse(vehicles));

      const result = await listVehicles();

      expect(fetch).toHaveBeenCalledWith("/api/vehicles", {
        credentials: "include",
      });
      expect(result).toEqual(vehicles);
    });

    it("throws on a non-OK response", async () => {
      vi.mocked(fetch).mockResolvedValue(new Response(null, { status: 500 }));

      await expect(listVehicles()).rejects.toThrow("Failed to list vehicles: 500");
    });
  });

  describe("getVehicle", () => {
    it("requests a single vehicle by id", async () => {
      const vehicle = { id: "1" };
      vi.mocked(fetch).mockResolvedValue(jsonResponse(vehicle));

      const result = await getVehicle("1");

      expect(fetch).toHaveBeenCalledWith("/api/vehicles/1", {
        credentials: "include",
      });
      expect(result).toEqual(vehicle);
    });

    it("throws on a non-OK response", async () => {
      vi.mocked(fetch).mockResolvedValue(new Response(null, { status: 404 }));

      await expect(getVehicle("1")).rejects.toThrow("Failed to get vehicle: 404");
    });
  });

  describe("createVehicle", () => {
    it("POSTs the JSON-serialized body", async () => {
      const body = { name: "My bike" };
      const created = { id: "1", ...body };
      vi.mocked(fetch).mockResolvedValue(jsonResponse(created));

      const result = await createVehicle(body);

      expect(fetch).toHaveBeenCalledWith("/api/vehicles", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify(body),
      });
      expect(result).toEqual(created);
    });

    it("throws an Error whose message includes the response body text", async () => {
      vi.mocked(fetch).mockResolvedValue(
        new Response("Vehicle name already exists", { status: 400 }),
      );

      await expect(createVehicle({ name: "dup" })).rejects.toThrow(
        "Vehicle name already exists",
      );
    });

    it("falls back to a generic message when the response body is empty", async () => {
      vi.mocked(fetch).mockResolvedValue(new Response("", { status: 500 }));

      await expect(createVehicle({ name: "x" })).rejects.toThrow(
        "Failed to create vehicle: 500",
      );
    });
  });

  describe("updateVehicle", () => {
    it("PUTs the JSON-serialized body to the vehicle's URL", async () => {
      const body = { name: "Updated" };
      const updated = { id: "1", ...body };
      vi.mocked(fetch).mockResolvedValue(jsonResponse(updated));

      const result = await updateVehicle("1", body);

      expect(fetch).toHaveBeenCalledWith("/api/vehicles/1", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify(body),
      });
      expect(result).toEqual(updated);
    });

    it("throws an Error whose message includes the response body text", async () => {
      vi.mocked(fetch).mockResolvedValue(
        new Response("Invalid payload", { status: 422 }),
      );

      await expect(updateVehicle("1", {})).rejects.toThrow("Invalid payload");
    });
  });

  describe("deleteVehicle", () => {
    it("DELETEs the vehicle's URL", async () => {
      vi.mocked(fetch).mockResolvedValue(new Response(null, { status: 204 }));

      await deleteVehicle("1");

      expect(fetch).toHaveBeenCalledWith("/api/vehicles/1", {
        method: "DELETE",
        credentials: "include",
      });
    });

    it("throws on a non-OK response", async () => {
      vi.mocked(fetch).mockResolvedValue(new Response(null, { status: 500 }));

      await expect(deleteVehicle("1")).rejects.toThrow(
        "Failed to delete vehicle: 500",
      );
    });
  });

  describe("getVehicleLocationHistory", () => {
    it("builds the limit/offset query string with defaults", async () => {
      const page = { items: [], total: 0 };
      vi.mocked(fetch).mockResolvedValue(jsonResponse(page));

      const result = await getVehicleLocationHistory("1");

      expect(fetch).toHaveBeenCalledWith(
        "/api/vehicles/1/locations?limit=5&offset=0",
        { credentials: "include" },
      );
      expect(result).toEqual(page);
    });

    it("builds the limit/offset query string with explicit values", async () => {
      vi.mocked(fetch).mockResolvedValue(jsonResponse({ items: [], total: 0 }));

      await getVehicleLocationHistory("1", { limit: 20, offset: 40 });

      expect(fetch).toHaveBeenCalledWith(
        "/api/vehicles/1/locations?limit=20&offset=40",
        { credentials: "include" },
      );
    });

    it("throws on a non-OK response", async () => {
      vi.mocked(fetch).mockResolvedValue(new Response(null, { status: 500 }));

      await expect(getVehicleLocationHistory("1")).rejects.toThrow(
        "Failed to get vehicle location history: 500",
      );
    });
  });

  describe("getSerTicketHistory", () => {
    it("builds the limit/offset query string with defaults", async () => {
      const page = { items: [], has_more: false };
      vi.mocked(fetch).mockResolvedValue(jsonResponse(page));

      const result = await getSerTicketHistory("1");

      expect(fetch).toHaveBeenCalledWith(
        "/api/vehicles/1/ser-tickets?limit=5&offset=0",
        { credentials: "include" },
      );
      expect(result).toEqual(page);
    });

    it("builds the limit/offset query string with explicit values", async () => {
      vi.mocked(fetch).mockResolvedValue(jsonResponse({ items: [], has_more: false }));

      await getSerTicketHistory("1", { limit: 20, offset: 40 });

      expect(fetch).toHaveBeenCalledWith(
        "/api/vehicles/1/ser-tickets?limit=20&offset=40",
        { credentials: "include" },
      );
    });

    it("throws on a non-OK response", async () => {
      vi.mocked(fetch).mockResolvedValue(new Response(null, { status: 500 }));

      await expect(getSerTicketHistory("1")).rejects.toThrow(
        "Failed to get SER ticket history: 500",
      );
    });
  });

  describe("getSerParkingExemption", () => {
    it("requests the exemption for a vehicle", async () => {
      const exemption = { exempt: true };
      vi.mocked(fetch).mockResolvedValue(jsonResponse(exemption));

      const result = await getSerParkingExemption("1");

      expect(fetch).toHaveBeenCalledWith(
        "/api/vehicles/1/ser-parking-exemptions",
        { credentials: "include" },
      );
      expect(result).toEqual(exemption);
    });

    it("throws on a non-OK response", async () => {
      vi.mocked(fetch).mockResolvedValue(new Response(null, { status: 404 }));

      await expect(getSerParkingExemption("1")).rejects.toThrow(
        "Failed to get SER parking exemption: 404",
      );
    });
  });

  describe("setSerParkingExemption", () => {
    it("POSTs the city/zone body", async () => {
      const exemption = { exempt: true };
      vi.mocked(fetch).mockResolvedValue(jsonResponse(exemption));

      const result = await setSerParkingExemption("1", "MAD", "3");

      expect(fetch).toHaveBeenCalledWith(
        "/api/vehicles/1/ser-parking-exemptions",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "include",
          body: JSON.stringify({ city_code: "MAD", zone_number: "3" }),
        },
      );
      expect(result).toEqual(exemption);
    });

    it("throws an Error whose message includes the response body text", async () => {
      vi.mocked(fetch).mockResolvedValue(
        new Response("Zone not found", { status: 404 }),
      );

      await expect(setSerParkingExemption("1", "MAD", "99")).rejects.toThrow(
        "Zone not found",
      );
    });
  });

  describe("clearSerParkingExemption", () => {
    it("DELETEs the exemption for a vehicle", async () => {
      vi.mocked(fetch).mockResolvedValue(new Response(null, { status: 204 }));

      await clearSerParkingExemption("1");

      expect(fetch).toHaveBeenCalledWith(
        "/api/vehicles/1/ser-parking-exemptions",
        { method: "DELETE", credentials: "include" },
      );
    });

    it("throws on a non-OK response", async () => {
      vi.mocked(fetch).mockResolvedValue(new Response(null, { status: 500 }));

      await expect(clearSerParkingExemption("1")).rejects.toThrow(
        "Failed to clear SER parking exemption: 500",
      );
    });
  });
});
