import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { createTelegramLinkCode, getConfiguredChannels } from "../../api/notifications";
import type { ConnectFlowProps } from "./registry";

// Bounded polling: ~2 minutes total at a 3s interval. See design.md decision 5
// — this is a new pattern for this frontend (no polling exists elsewhere), so
// it must not poll forever and must clean up its interval on unmount.
const POLL_INTERVAL_MS = 3000;
const MAX_POLL_ATTEMPTS = 40;

export default function TelegramConnectFlow({ onClose, onConnected }: ConnectFlowProps) {
  const { t } = useTranslation();
  const [deepLink, setDeepLink] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [timedOut, setTimedOut] = useState(false);

  // Fetch the deep link once on mount.
  useEffect(() => {
    let cancelled = false;

    async function init() {
      try {
        const { deep_link } = await createTelegramLinkCode();
        if (!cancelled) {
          setDeepLink(deep_link);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : t("modal.connectTelegram.linkError"));
        }
      }
    }
    void init();

    return () => {
      cancelled = true;
    };
  }, [t]);

  // Poll for link confirmation once we have a deep link to show. Cleans up
  // the interval on unmount and stops itself after MAX_POLL_ATTEMPTS.
  useEffect(() => {
    if (!deepLink) {
      return;
    }

    let cancelled = false;
    let attempts = 0;

    const intervalId = window.setInterval(() => {
      void (async () => {
        attempts += 1;
        try {
          const { channels } = await getConfiguredChannels();
          if (cancelled) {
            return;
          }
          if (channels.includes("telegram")) {
            window.clearInterval(intervalId);
            onConnected("telegram");
            onClose();
            return;
          }
        } catch {
          // Transient polling errors are ignored; we keep retrying until timeout.
        }
        if (!cancelled && attempts >= MAX_POLL_ATTEMPTS) {
          window.clearInterval(intervalId);
          setTimedOut(true);
        }
      })();
    }, POLL_INTERVAL_MS);

    return () => {
      cancelled = true;
      window.clearInterval(intervalId);
    };
  }, [deepLink, onClose, onConnected]);

  const title = t("modal.connectTelegram.title");

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={title}
      className="fixed inset-0 z-[1001] flex items-center justify-center bg-black/40"
    >
      <div className="w-full max-w-md rounded bg-white p-6 shadow-lg">
        <h2 className="mb-4 text-lg font-semibold">{title}</h2>

        {error && (
          <p role="alert" className="mb-4 text-sm text-red-600">
            {error}
          </p>
        )}

        {!error && !deepLink && (
          <p className="text-sm text-gray-600">{t("modal.connectTelegram.generatingLink")}</p>
        )}

        {!error && deepLink && (
          <div className="space-y-3">
            <p className="text-sm text-gray-600">{t("modal.connectTelegram.instructions")}</p>
            <a
              href={deepLink}
              target="_blank"
              rel="noreferrer"
              className="block break-all rounded bg-blue-50 px-3 py-2 text-sm text-blue-700 underline"
            >
              {deepLink}
            </a>
            {timedOut ? (
              <p role="alert" className="text-sm text-amber-600">
                {t("modal.connectTelegram.stillWaiting")}
              </p>
            ) : (
              <p className="text-sm text-gray-500">{t("modal.connectTelegram.waiting")}</p>
            )}
          </div>
        )}

        <div className="flex justify-end pt-4">
          <button
            type="button"
            onClick={onClose}
            className="rounded bg-gray-100 px-4 py-2 text-sm hover:bg-gray-200"
          >
            {t("common.close")}
          </button>
        </div>
      </div>
    </div>
  );
}
