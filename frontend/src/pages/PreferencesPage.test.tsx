import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { getMe } from "../api/auth";
import { getAvailableLanguages, getConfiguredChannels } from "../api/notifications";
import { getNotificationPreferences, getNotificationTypes } from "../api/notificationPreferences";
import { getPreferences, updatePreferences } from "../api/preferences";
import { renderWithProviders, screen, waitFor, within } from "../test/render";
import PreferencesPage from "./PreferencesPage";

vi.mock("../api/auth");
vi.mock("../api/notifications");
vi.mock("../api/notificationPreferences");
vi.mock("../api/preferences");

const basePreferences = {
  default_ticket_duration_minutes: 60,
  auto_create_ticket: false,
  preferred_notification_channel: null,
  notification_language: null,
  timezone: null,
};

function mockHappyPathLoad() {
  vi.mocked(getMe).mockResolvedValue(null);
  vi.mocked(getPreferences).mockResolvedValue(basePreferences);
  vi.mocked(getConfiguredChannels).mockResolvedValue({ channels: [] });
  vi.mocked(getAvailableLanguages).mockResolvedValue({ languages: [] });
  vi.mocked(getNotificationTypes).mockResolvedValue([]);
  vi.mocked(getNotificationPreferences).mockResolvedValue([]);
}

function getTimezoneCombobox() {
  return screen.getByRole("combobox", { name: /timezone/i });
}

async function renderPreferencesPage() {
  const result = renderWithProviders(<PreferencesPage />, {
    withAuth: true,
    withRouter: true,
  });
  await screen.findByRole("combobox", { name: /timezone/i });
  return result;
}

describe("PreferencesPage timezone combobox", () => {
  beforeEach(() => {
    mockHappyPathLoad();
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it("live-filters the visible option list as the user types, without needing to reopen the dropdown", async () => {
    const user = userEvent.setup();
    await renderPreferencesPage();

    const combobox = getTimezoneCombobox();
    await user.click(combobox);

    const listbox = await screen.findByRole("listbox");
    const optionsBefore = within(listbox).getAllByRole("option");
    expect(optionsBefore.length).toBeGreaterThan(1);

    // Type without clicking/reopening the combobox again — the dropdown
    // must already be open and its option list must live-update.
    await user.type(combobox, "madrid");

    await waitFor(() => {
      const optionsAfter = within(screen.getByRole("listbox")).getAllByRole("option");
      expect(optionsAfter.length).toBe(1);
      expect(optionsAfter[0]).toHaveTextContent(/Europe\/Madrid/i);
    });

    // The dropdown never had to be closed and reopened to reflect the filter.
    expect(getTimezoneCombobox()).toHaveAttribute("aria-expanded", "true");
  });

  it("commits the top matching option on Enter without triggering a save request", async () => {
    const user = userEvent.setup();
    await renderPreferencesPage();

    const combobox = getTimezoneCombobox();
    await user.click(combobox);
    await user.type(combobox, "madrid");

    await waitFor(() => {
      expect(within(screen.getByRole("listbox")).getAllByRole("option")).toHaveLength(1);
    });

    await user.keyboard("{Enter}");

    await waitFor(() => {
      expect((combobox as HTMLInputElement).value).toContain("Europe/Madrid");
    });

    expect(updatePreferences).not.toHaveBeenCalled();
  });
});
