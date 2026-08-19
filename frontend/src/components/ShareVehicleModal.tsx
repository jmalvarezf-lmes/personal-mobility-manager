import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { listVehicleShares, revokeVehicleShare, shareVehicle } from "../api/vehicles";
import type { VehicleSharee } from "../types/vehicle";
import Button from "./ui/Button";
import Input from "./ui/Input";

interface ShareVehicleModalProps {
  vehicleId: string;
  onClose: () => void;
}

export default function ShareVehicleModal({ vehicleId, onClose }: ShareVehicleModalProps) {
  const { t } = useTranslation();
  const [email, setEmail] = useState("");
  const [sharees, setSharees] = useState<VehicleSharee[]>([]);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [removingUserId, setRemovingUserId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    listVehicleShares(vehicleId)
      .then((response) => {
        if (!cancelled) setSharees(response.sharees);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : t("modal.shareVehicle.loadError"));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [vehicleId, t]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const response = await shareVehicle(vehicleId, email.trim());
      setSharees(response.sharees);
      setEmail("");
    } catch (err) {
      setError(err instanceof Error ? err.message : t("modal.shareVehicle.shareError"));
    } finally {
      setSubmitting(false);
    }
  }

  async function handleRevoke(userId: string) {
    setError(null);
    setRemovingUserId(userId);
    try {
      await revokeVehicleShare(vehicleId, userId);
      setSharees((prev) => prev.filter((s) => s.user_id !== userId));
    } catch (err) {
      setError(err instanceof Error ? err.message : t("modal.shareVehicle.revokeError"));
    } finally {
      setRemovingUserId((prev) => (prev === userId ? null : prev));
    }
  }

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={t("modal.shareVehicle.title")}
      className="fixed inset-0 z-[1001] flex items-center justify-center bg-black/40"
    >
      <div className="w-full max-w-md rounded bg-white p-6 shadow-lg">
        <h2 className="mb-4 text-lg font-semibold">{t("modal.shareVehicle.title")}</h2>

        <form onSubmit={(e) => void handleSubmit(e)} className="space-y-3">
          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700" htmlFor="share-email">
              {t("common.email")}
            </label>
            <Input
              id="share-email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder={t("modal.shareVehicle.emailPlaceholder")}
              required
            />
          </div>

          {error && (
            <p role="alert" className="text-sm text-red-600">
              {error}
            </p>
          )}

          <div className="flex justify-end gap-2">
            <Button type="button" variant="secondary" onClick={onClose}>
              {t("common.close")}
            </Button>
            <Button type="submit" disabled={submitting || !email.trim()}>
              {submitting ? t("modal.shareVehicle.sharing") : t("modal.shareVehicle.share")}
            </Button>
          </div>
        </form>

        <div className="mt-6">
          <h3 className="mb-2 text-sm font-semibold text-gray-700">
            {t("modal.shareVehicle.shareesTitle")}
          </h3>
          {loading ? (
            <p className="text-sm text-gray-500">{t("modal.shareVehicle.loading")}</p>
          ) : sharees.length === 0 ? (
            <p className="text-sm text-gray-500">{t("modal.shareVehicle.noSharees")}</p>
          ) : (
            <ul className="space-y-2">
              {sharees.map((sharee) => (
                <li
                  key={sharee.user_id}
                  className="flex items-center justify-between rounded border border-gray-200 px-3 py-2"
                >
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium text-gray-800">
                      {sharee.display_name}
                    </p>
                    <p className="truncate text-xs text-gray-500">{sharee.email}</p>
                  </div>
                  <Button
                    type="button"
                    variant="danger"
                    size="sm"
                    disabled={removingUserId === sharee.user_id}
                    onClick={() => void handleRevoke(sharee.user_id)}
                  >
                    {removingUserId === sharee.user_id
                      ? t("modal.shareVehicle.removing")
                      : t("modal.shareVehicle.remove")}
                  </Button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}
