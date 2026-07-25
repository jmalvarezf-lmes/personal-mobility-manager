import { describe, expect, it } from "vitest";
import { injectApiServer } from "./openapi";

describe("injectApiServer", () => {
  it("sets servers on a spec with no existing servers key", () => {
    const spec = { openapi: "3.1.0", paths: {} };

    const result = injectApiServer(spec);

    expect(result.servers).toEqual([{ url: "/api" }]);
  });

  it("overwrites, rather than appends to, a pre-existing servers key", () => {
    const spec = {
      openapi: "3.1.0",
      paths: {},
      servers: [{ url: "http://example.com" }, { url: "http://other.example.com" }],
    };

    const result = injectApiServer(spec);

    expect(result.servers).toEqual([{ url: "/api" }]);
  });
});
