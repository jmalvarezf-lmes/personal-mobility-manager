import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { getMe } from "../api/auth";
import { getAvailableLanguages, getConfiguredChannels } from "../api/notifications";
import { getNotificationPreferences, getNotificationTypes } from "../api/notificationPreferences";
import { getPreferences, PreferencesUpdateError, updatePreferences } from "../api/preferences";
import { renderWithProviders, screen, waitFor, within } from "../test/render";
import PreferencesPage from "./PreferencesPage";

vi.mock("../api/auth");
vi.mock("../api/notifications");
vi.mock("../api/notificationPreferences");
// Explicit factory (rather than bare `vi.mock("../api/preferences")`) so the
// real `PreferencesUpdateError` class — and its prototype chain, needed for
// `instanceof Error`/`instanceof PreferencesUpdateError` checks — survives;
// automocking a class export replaces it with a stub that breaks both.
vi.mock("../api/preferences", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../api/preferences")>();
  return {
    ...actual,
    getPreferences: vi.fn(),
    updatePreferences: vi.fn(),
  };
});

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

const _NOTIFICATION_TYPES = [
  { key: "ser_zone_ticket_required", label: "SER ticket required", config_schema: {} },
  { key: "ser_ticket_created", label: "SER ticket created", config_schema: {} },
  { key: "ser_ticket_creation_failed", label: "SER ticket creation failed", config_schema: {} },
];

function mockLoadWithNotificationTypes(autoCreateTicket: boolean) {
  vi.mocked(getMe).mockResolvedValue(null);
  vi.mocked(getPreferences).mockResolvedValue({ ...basePreferences, auto_create_ticket: autoCreateTicket });
  vi.mocked(getConfiguredChannels).mockResolvedValue({ channels: [] });
  vi.mocked(getAvailableLanguages).mockResolvedValue({ languages: [] });
  vi.mocked(getNotificationTypes).mockResolvedValue(_NOTIFICATION_TYPES);
  vi.mocked(getNotificationPreferences).mockResolvedValue(
    _NOTIFICATION_TYPES.map((type) => ({ type_key: type.key, enabled: false, config: {} })),
  );
}

describe("PreferencesPage auto_create_ticket lock behavior", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("greys out ser_zone_ticket_required when auto_create_ticket is true on load", async () => {
    mockLoadWithNotificationTypes(true);
    renderWithProviders(<PreferencesPage />, { withAuth: true, withRouter: true });

    const zoneRequired = await screen.findByLabelText("SER ticket required");
    const ticketCreated = screen.getByLabelText("SER ticket created");
    const ticketCreationFailed = screen.getByLabelText("SER ticket creation failed");

    expect(zoneRequired).toBeDisabled();
    expect(ticketCreated).not.toBeDisabled();
    expect(ticketCreationFailed).not.toBeDisabled();
  });

  it("greys out the two new SER-ticket types when auto_create_ticket is false on load", async () => {
    mockLoadWithNotificationTypes(false);
    renderWithProviders(<PreferencesPage />, { withAuth: true, withRouter: true });

    const zoneRequired = await screen.findByLabelText("SER ticket required");
    const ticketCreated = screen.getByLabelText("SER ticket created");
    const ticketCreationFailed = screen.getByLabelText("SER ticket creation failed");

    expect(zoneRequired).not.toBeDisabled();
    expect(ticketCreated).toBeDisabled();
    expect(ticketCreationFailed).toBeDisabled();
  });

  it("updates the disabled state immediately when auto_create_ticket is toggled before saving", async () => {
    const user = userEvent.setup();
    mockLoadWithNotificationTypes(false);
    renderWithProviders(<PreferencesPage />, { withAuth: true, withRouter: true });

    const autoCreateCheckbox = await screen.findByLabelText(/automatically create/i);
    const ticketCreated = screen.getByLabelText("SER ticket created");
    expect(ticketCreated).toBeDisabled();

    await user.click(autoCreateCheckbox);

    await waitFor(() => {
      expect(screen.getByLabelText("SER ticket created")).not.toBeDisabled();
      expect(screen.getByLabelText("SER ticket required")).toBeDisabled();
    });
  });
});

describe("PreferencesPage save error surfacing", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("surfaces the PUT /preferences 422 no-provider rejection message via the error area", async () => {
    const user = userEvent.setup();
    mockHappyPathLoad();
    vi.mocked(updatePreferences).mockRejectedValue(
      new PreferencesUpdateError(
        "Connect a SER ticket provider before enabling automatic ticket creation.",
        "ser_provider_not_connected",
      ),
    );
    renderWithProviders(<PreferencesPage />, { withAuth: true, withRouter: true });

    await screen.findByRole("combobox", { name: /timezone/i });
    const autoCreateCheckbox = screen.getByLabelText(/automatically create/i);
    await user.click(autoCreateCheckbox);
    await user.click(screen.getByRole("button", { name: /save/i }));

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Connect a SER ticket provider before enabling automatic ticket creation.");
  });
});
