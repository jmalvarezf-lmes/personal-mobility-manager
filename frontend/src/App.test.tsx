import { afterEach, describe, expect, it, vi } from "vitest";

import { getMe } from "./api/auth";
import { getAvailableLanguages, getConfiguredChannels } from "./api/notifications";
import { getNotificationPreferences, getNotificationTypes } from "./api/notificationPreferences";
import { getPreferences } from "./api/preferences";
import App from "./App";
import { renderWithProviders, screen } from "./test/render";

vi.mock("./api/auth");
vi.mock("./api/notifications");
vi.mock("./api/notificationPreferences");
vi.mock("./api/preferences");

function setPath(path: string) {
  window.history.pushState({}, "", path);
}

describe("App routing", () => {
  afterEach(() => {
    vi.clearAllMocks();
    setPath("/");
  });

  it("renders the landing page at the root path", async () => {
    vi.mocked(getMe).mockResolvedValue(null);

    renderWithProviders(<App />);

    expect(
      await screen.findByRole("heading", {
        level: 1,
        name: "Track, park, and get notified — all your mobility, one place",
      }),
    ).toBeInTheDocument();
  });

  it("redirects an unauthenticated user away from a protected route to the landing page", async () => {
    vi.mocked(getMe).mockResolvedValue(null);
    setPath("/my-vehicles");

    renderWithProviders(<App />);

    expect(
      await screen.findByRole("heading", {
        level: 1,
        name: "Track, park, and get notified — all your mobility, one place",
      }),
    ).toBeInTheDocument();
  });

  it("renders a protected page for an authenticated user", async () => {
    vi.mocked(getMe).mockResolvedValue({
      id: "1",
      email: "user@example.com",
      display_name: "User",
    });
    vi.mocked(getPreferences).mockResolvedValue({
      default_ticket_duration_minutes: 60,
      auto_create_ticket: false,
      preferred_notification_channel: null,
      notification_language: null,
      timezone: null,
    });
    vi.mocked(getConfiguredChannels).mockResolvedValue({ channels: [] });
    vi.mocked(getAvailableLanguages).mockResolvedValue({ languages: [] });
    vi.mocked(getNotificationTypes).mockResolvedValue([]);
    vi.mocked(getNotificationPreferences).mockResolvedValue([]);
    setPath("/preferences");

    renderWithProviders(<App />);

    expect(
      await screen.findByRole("combobox", { name: /timezone/i }),
    ).toBeInTheDocument();
  });
});
