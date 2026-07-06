import type { ComponentType } from "react";
import TelegramConnectFlow from "./TelegramConnectFlow";

export interface ConnectFlowProps {
  onClose: () => void;
  onConnected: (channel: string) => void;
}

// Channel-id -> connect-flow-component registry. This is unavoidably
// channel-specific code (each channel's connect flow has a different shape:
// Telegram's is an async deep-link-then-webhook flow, a future channel might
// be a synchronous form) — it is NOT the same thing as hardcoding which
// channels exist. The list of *rows* on the page still comes from
// GET /notifications/available-channels; an id present in that catalog with
// no entry here renders a disabled/"not yet supported" row instead of
// crashing (see NotificationChannelsPage).
export const CONNECT_FLOW_REGISTRY: Record<string, ComponentType<ConnectFlowProps>> = {
  telegram: TelegramConnectFlow,
};
