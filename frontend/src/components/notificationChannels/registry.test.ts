import { describe, expect, it } from "vitest";

import TelegramConnectFlow from "./TelegramConnectFlow";
import { CONNECT_FLOW_REGISTRY } from "./registry";

describe("CONNECT_FLOW_REGISTRY", () => {
  it("maps 'telegram' to TelegramConnectFlow", () => {
    expect(CONNECT_FLOW_REGISTRY.telegram).toBe(TelegramConnectFlow);
  });

  it("has no entry for an unknown channel id", () => {
    expect(CONNECT_FLOW_REGISTRY["unknown-channel"]).toBeUndefined();
  });
});
