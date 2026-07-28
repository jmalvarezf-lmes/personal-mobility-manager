import { useEffect, useMemo, useState, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { getPreferences } from "../api/preferences";
import { resolveDisplayTimezone } from "../utils/timezone";

// Shared by every paginated history modal (vehicle location history, SER
// ticket history, ...) — see add-ser-ticket-history-ui tasks.md task 14.3.
export const OSM_FALLBACK = "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png";
export const PAGE_SIZE = 5;

export interface HistoryPage<T> {
  items: T[];
  has_more: boolean;
}

export interface HistoryModalMessages {
  loading: string;
  loadingMore: string;
  loadMore: string;
  empty: string;
  /** Fallback text used when a fetch fails without an `Error.message`. */
  error: string;
}

export interface HistoryModalRenderArgs<T> {
  items: T[];
  displayTimezone: string;
}

interface HistoryModalProps<T> {
  /** Used as both the dialog's `aria-label` and its visible heading. */
  title: string;
  onClose: () => void;
  vehicleId: string;
  /** `(vehicleId, { limit, offset }) => Promise<{ items, has_more }>` — same shape as `getVehicleLocationHistory`/`getSerTicketHistory`. */
  fetchPage: (vehicleId: string, opts: { limit: number; offset: number }) => Promise<HistoryPage<T>>;
  messages: HistoryModalMessages;
  /** Class applied to the wrapper around the per-item content + load-more button — differs slightly per modal (e.g. `overflow-hidden` vs `overflow-y-auto`). */
  contentClassName: string;
  /** Render-prop for the per-item content (map + list rows, ticket cards, ...). Only invoked once the first page has loaded and is non-empty. */
  children: (args: HistoryModalRenderArgs<T>) => ReactNode;
}

export default function HistoryModal<T>({
  title,
  onClose,
  vehicleId,
  fetchPage,
  messages,
  contentClassName,
  children,
}: HistoryModalProps<T>) {
  const { t } = useTranslation();
  const [items, setItems] = useState<T[]>([]);
  const [offset, setOffset] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // The user's saved timezone preference, if any — fetched once and merged
  // into the resolution cascade below. Left null if the fetch fails, which
  // simply falls through to the browser-detected/UTC fallback.
  const [savedTimezone, setSavedTimezone] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    getPreferences()
      .then((prefs) => {
        if (!cancelled) setSavedTimezone(prefs.timezone);
      })
      .catch(() => {
        // Fall back to browser detection / UTC — see resolveDisplayTimezone.
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // Resolved once per render from the saved preference; formatInTimezone
  // itself computes each row's abbreviation per that row's own date, so
  // this value is just the zone name, not a cached formatted string.
  const displayTimezone = useMemo(() => resolveDisplayTimezone(savedTimezone), [savedTimezone]);

  useEffect(() => {
    let cancelled = false;
    fetchPage(vehicleId, { limit: PAGE_SIZE, offset: 0 })
      .then((page) => {
        if (cancelled) return;
        setItems(page.items);
        setHasMore(page.has_more);
        setOffset(page.items.length);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : messages.error);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
    // Reload from scratch whenever a fresh modal instance mounts for this
    // vehicle — closing and reopening discards any previously loaded pages.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [vehicleId]);

  async function handleLoadMore() {
    setLoadingMore(true);
    setError(null);
    try {
      const page = await fetchPage(vehicleId, { limit: PAGE_SIZE, offset });
      setItems((prev) => [...prev, ...page.items]);
      setHasMore(page.has_more);
      setOffset((prev) => prev + page.items.length);
    } catch (err) {
      setError(err instanceof Error ? err.message : messages.error);
    } finally {
      setLoadingMore(false);
    }
  }

  const isEmpty = !loading && items.length === 0 && !error;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={title}
      className="fixed inset-0 z-[1001] flex items-center justify-center bg-black/40"
    >
      <div className="flex max-h-[85vh] w-full max-w-lg flex-col rounded bg-white p-6 shadow-lg">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold">{title}</h2>
          <button
            type="button"
            onClick={onClose}
            className="rounded bg-gray-100 px-3 py-1 text-sm hover:bg-gray-200"
          >
            {t("common.cancel")}
          </button>
        </div>

        {error && (
          <p role="alert" className="mb-3 text-sm text-red-600">
            {error}
          </p>
        )}

        {loading && <p className="text-sm text-gray-500">{messages.loading}</p>}

        {isEmpty && <p className="text-sm italic text-gray-400">{messages.empty}</p>}

        {!loading && items.length > 0 && (
          <div className={contentClassName}>
            {children({ items, displayTimezone })}

            {hasMore && (
              <button
                type="button"
                onClick={() => void handleLoadMore()}
                disabled={loadingMore}
                className="rounded bg-gray-100 px-4 py-2 text-sm hover:bg-gray-200 disabled:opacity-50"
              >
                {loadingMore ? messages.loadingMore : messages.loadMore}
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
