import { useState } from "react";
import { useTranslation } from "react-i18next";
import { connect } from "../api/serTicketProviders";
import Button from "./ui/Button";
import Input from "./ui/Input";

interface ConnectSerProviderModalProps {
  provider: string;
  providerDisplayName: string;
  onClose: () => void;
  onConnected: (provider: string) => void;
}

export default function ConnectSerProviderModal({
  provider,
  providerDisplayName,
  onClose,
  onConnected,
}: ConnectSerProviderModalProps) {
  const { t } = useTranslation();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await connect({ provider, email, password });
      onConnected(provider);
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("page.serProviders.connectError"));
    } finally {
      setSubmitting(false);
    }
  }

  const title = t("modal.connectSerProvider.title", { provider: providerDisplayName });

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={title}
      className="fixed inset-0 z-[1001] flex items-center justify-center bg-black/40"
    >
      <div className="w-full max-w-md rounded bg-white p-6 shadow-lg">
        <h2 className="mb-4 text-lg font-semibold">{title}</h2>
        <form onSubmit={(e) => void handleSubmit(e)} className="space-y-3">
          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700" htmlFor="ser-provider-email">
              {t("common.email")}
            </label>
            <Input
              id="ser-provider-email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </div>

          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700" htmlFor="ser-provider-password">
              {t("common.password")}
            </label>
            <Input
              id="ser-provider-password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </div>

          {error && (
            <p role="alert" className="text-sm text-red-600">
              {error}
            </p>
          )}

          <div className="flex justify-end gap-2 pt-2">
            <Button type="button" variant="secondary" onClick={onClose}>
              {t("common.cancel")}
            </Button>
            <Button type="submit" disabled={submitting}>
              {submitting ? t("modal.connectSerProvider.connecting") : t("modal.connectSerProvider.connect")}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
