import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { getPreferences } from "../api/preferences";
import { renderWithProviders, screen, waitFor } from "../test/render";
import HistoryModal, { type HistoryPage } from "./HistoryModal";

vi.mock("../api/preferences");

interface Item {
  id: string;
}

const messages = {
  loading: "Loading…",
  loadingMore: "Loading more…",
  loadMore: "Load more",
  empty: "Nothing here",
  error: "Something went wrong",
};

const noop = () => undefined;

function renderModal(fetchPage: (
  vehicleId: string,
  opts: { limit: number; offset: number },
) => Promise<HistoryPage<Item>>) {
  return renderWithProviders(
    <HistoryModal<Item>
      title="Test modal"
      onClose={noop}
      vehicleId="veh-1"
      fetchPage={fetchPage}
      contentClassName="content"
      messages={messages}
    >
      {({ items }) => (
        <ul>
          {items.map((item) => (
            <li key={item.id}>{item.id}</li>
          ))}
        </ul>
      )}
    </HistoryModal>,
  );
}

describe("HistoryModal", () => {
  beforeEach(() => {
    vi.mocked(getPreferences).mockResolvedValue({
      default_ticket_duration_minutes: 60,
      auto_create_ticket: false,
      preferred_notification_channel: null,
      notification_language: null,
      timezone: "UTC",
    });
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it("renders the dialog shell with the given title", async () => {
    const fetchPage = vi.fn().mockResolvedValue({ items: [{ id: "a" }], has_more: false });

    renderModal(fetchPage);

    const dialog = await screen.findByRole("dialog");
    expect(dialog).toHaveAttribute("aria-modal", "true");
    expect(screen.getByRole("heading", { name: "Test modal" })).toBeInTheDocument();
  });

  it("fetches the first page on mount with the default page size", async () => {
    const fetchPage = vi.fn().mockResolvedValue({ items: [{ id: "a" }], has_more: false });

    renderModal(fetchPage);

    await waitFor(() => {
      expect(fetchPage).toHaveBeenCalledWith("veh-1", { limit: 5, offset: 0 });
    });
    expect(await screen.findByText("a")).toBeInTheDocument();
  });

  it("shows the empty message when the first page has no items", async () => {
    const fetchPage = vi.fn().mockResolvedValue({ items: [], has_more: false });

    renderModal(fetchPage);

    expect(await screen.findByText(messages.empty)).toBeInTheDocument();
  });

  it("shows the error fallback message when the fetch rejects without an Error", async () => {
    const fetchPage = vi.fn().mockRejectedValue("boom");

    renderModal(fetchPage);

    expect(await screen.findByRole("alert")).toHaveTextContent(messages.error);
  });

  it("paginates via load-more, appending items and advancing the offset", async () => {
    const fetchPage = vi
      .fn()
      .mockResolvedValueOnce({ items: [{ id: "a" }], has_more: true })
      .mockResolvedValueOnce({ items: [{ id: "b" }], has_more: false });

    renderModal(fetchPage);

    const loadMore = await screen.findByRole("button", { name: messages.loadMore });
    loadMore.click();

    await waitFor(() => {
      expect(fetchPage).toHaveBeenCalledWith("veh-1", { limit: 5, offset: 1 });
    });
    expect(await screen.findByText("a")).toBeInTheDocument();
    expect(await screen.findByText("b")).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.queryByRole("button", { name: messages.loadMore })).not.toBeInTheDocument();
    });
  });

  it("calls onClose when the cancel button is clicked", async () => {
    const fetchPage = vi.fn().mockResolvedValue({ items: [{ id: "a" }], has_more: false });
    const onClose = vi.fn();

    renderWithProviders(
      <HistoryModal<Item>
        title="Test modal"
        onClose={onClose}
        vehicleId="veh-1"
        fetchPage={fetchPage}
        contentClassName="content"
        messages={messages}
      >
        {({ items }) => <ul>{items.map((item) => <li key={item.id}>{item.id}</li>)}</ul>}
      </HistoryModal>,
    );

    const cancelButton = await screen.findByRole("button", { name: /cancel/i });
    cancelButton.click();

    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
