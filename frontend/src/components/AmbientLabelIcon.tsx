import { useState } from "react";
import { useTranslation } from "react-i18next";

interface AmbientLabelIconProps {
  /**
   * Resolved ambient label value ("A"/"B"/"C"/"ECO"/"0"), or null/undefined
   * when unresolved. `undefined` is accepted (not just `null`) because the
   * vehicle-creation response is a leaner schema that omits this field
   * entirely — see MyVehiclesPage.handleCreated.
   */
  label: string | null | undefined;
}

/**
 * Renders a vehicle's DGT ambient label:
 * - B/C/ECO/0: the cached sticker icon, fetched from our own API (never
 *   hotlinking DGT directly — see add-ambient-label-lookup design.md
 *   decision 9). A 404 (uncached icon) is tolerated by hiding the element.
 * - A: a "no label" text indicator, no icon requested (category A has no sticker).
 * - unresolved (null): nothing rendered.
 */
export default function AmbientLabelIcon({ label }: AmbientLabelIconProps) {
  const { t } = useTranslation();
  const [iconFailed, setIconFailed] = useState(false);

  if (!label) {
    return null;
  }

  if (label === "A") {
    return (
      <span className="text-sm italic text-gray-400" data-testid="ambient-label-none">
        {t("vehicle.noAmbientLabel")}
      </span>
    );
  }

  if (iconFailed) {
    return null;
  }

  return (
    <img
      src={`/api/ambient-labels/${label}/icon`}
      alt={t("vehicle.ambientLabelIconAlt", { label })}
      onError={() => setIconFailed(true)}
      className="h-8 w-8 flex-shrink-0 object-contain"
    />
  );
}
