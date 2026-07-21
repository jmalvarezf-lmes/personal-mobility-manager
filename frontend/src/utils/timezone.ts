/**
 * Client-side timezone resolution + formatting.
 *
 * No date/timezone library — everything here uses the native `Intl` API.
 * See openspec/changes/add-user-timezone-preference/design.md for the
 * rationale behind the resolution cascade and the two distinct call sites
 * for timezone-abbreviation computation (per-row vs. picker-label "now").
 */

const FALLBACK_ZONE = "UTC";

// `Intl`'s `timeZoneName: 'short'` abbreviation is locale-dependent CLDR
// data: for many locales (including plain "en"/"en-US", a common browser
// default) most IANA zones resolve to a generic "GMT+1"/"GMT+2" offset
// rather than a named abbreviation like "CEST". "en-GB" reliably carries
// the named abbreviation, so it's used as the default whenever a caller
// doesn't explicitly request a different locale — this only affects which
// abbreviation/digit style is used, not correctness of the underlying
// instant or offset.
const DEFAULT_LOCALE = "en-GB";

// Used only if the runtime lacks `Intl.supportedValuesOf` (a relatively
// recent API) — degrades the picker to a short list rather than throwing.
// The resolution cascade below is unaffected either way.
const FALLBACK_TIMEZONES = [
  "UTC",
  "Europe/Madrid",
  "Europe/London",
  "America/New_York",
  "America/Los_Angeles",
  "Asia/Tokyo",
];

export interface TimezoneOption {
  /** IANA zone identifier, e.g. "Europe/Madrid". */
  value: string;
  /** Display label, e.g. "Europe/Madrid (CEST)". */
  label: string;
}

/**
 * Resolve the timezone to display timestamps in:
 * saved user preference -> browser-detected timezone -> UTC.
 *
 * Computed at call time, nothing is persisted as a side effect.
 */
export function resolveDisplayTimezone(preference: string | null | undefined): string {
  if (preference) {
    return preference;
  }
  try {
    const detected = Intl.DateTimeFormat().resolvedOptions().timeZone;
    if (detected) {
      return detected;
    }
  } catch {
    // Detection can throw in odd environments — fall through to UTC.
  }
  return FALLBACK_ZONE;
}

/**
 * The abbreviation `zone` uses for `date` (e.g. "CEST" or "CET"), computed
 * against that specific instant — the same IANA zone's abbreviation shifts
 * across DST boundaries, so this must never be cached per-zone.
 */
function zoneAbbreviation(date: Date, zone: string, locale?: string): string {
  try {
    const parts = new Intl.DateTimeFormat(locale ?? DEFAULT_LOCALE, {
      timeZone: zone,
      timeZoneName: "short",
    }).formatToParts(date);
    return parts.find((part) => part.type === "timeZoneName")?.value ?? zone;
  } catch {
    return zone;
  }
}

/**
 * Format `date` as `{year}-{month}-{day} {hour}:{minute}` in `zone`,
 * using a fixed set of numeric parts so the result never depends on
 * `Intl`'s locale-specific field ordering.
 */
function formatDateTimeParts(date: Date, zone: string, locale: string): string {
  const parts = new Intl.DateTimeFormat(locale, {
    timeZone: zone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  }).formatToParts(date);
  const get = (type: string) => parts.find((part) => part.type === type)?.value ?? "";
  return `${get("year")}-${get("month")}-${get("day")} ${get("hour")}:${get("minute")}`;
}

/**
 * Format `isoString` in `zone` as a full date + time, suffixed with that
 * zone's abbreviation for this specific instant's date (e.g.
 * "2026-07-15 14:32 CEST"). Computed fresh on every call — never cached —
 * since the abbreviation depends on both zone and instant (DST), and the
 * calendar date itself can shift relative to the source UTC instant
 * depending on the zone.
 *
 * `zone` ultimately comes from a saved user preference, which the backend
 * validates against Python's `zoneinfo.available_timezones()` — a broader
 * set than what every browser's `Intl` implementation recognizes. If `zone`
 * isn't recognized here, this falls back to formatting in UTC rather than
 * throwing during render (there is no error boundary in this app).
 */
export function formatInTimezone(isoString: string, zone: string, locale?: string): string {
  const date = new Date(isoString);
  const effectiveLocale = locale ?? DEFAULT_LOCALE;
  let targetZone = zone;
  let dateTime: string;
  try {
    dateTime = formatDateTimeParts(date, targetZone, effectiveLocale);
  } catch {
    targetZone = FALLBACK_ZONE;
    dateTime = formatDateTimeParts(date, targetZone, effectiveLocale);
  }
  const abbreviation = zoneAbbreviation(date, targetZone, effectiveLocale);
  return `${dateTime} ${abbreviation}`;
}

/**
 * List every IANA timezone available via `Intl.supportedValuesOf('timeZone')`,
 * each labeled `"<Zone> (<current abbreviation>)"` for use in a picker. The
 * abbreviation shown here is evaluated against *today's* date — a label for
 * zone selection, not a stored value — distinct from the per-instant
 * abbreviation `formatInTimezone` computes for each displayed timestamp.
 *
 * Falls back to a small hardcoded zone list if `Intl.supportedValuesOf` is
 * unavailable, rather than throwing.
 */
export function listTimezoneOptions(locale?: string): TimezoneOption[] {
  let zones: string[];
  try {
    zones =
      typeof Intl.supportedValuesOf === "function"
        ? Intl.supportedValuesOf("timeZone")
        : FALLBACK_TIMEZONES;
  } catch {
    zones = FALLBACK_TIMEZONES;
  }

  const now = new Date();
  return zones.map((zone) => ({
    value: zone,
    label: `${zone} (${zoneAbbreviation(now, zone, locale)})`,
  }));
}
