import { expect, test } from "@playwright/test";
import { formatInTimezone, resolveDisplayTimezone } from "../src/utils/timezone";

/**
 * Unit-style tests for `src/utils/timezone.ts`.
 *
 * The project has no vitest/jest setup (only Playwright e2e + tsc/eslint),
 * and adding a whole new test runner just for a handful of pure-function
 * assertions felt like the wrong tradeoff given design.md's explicit
 * "no new dependency" stance for this change. Playwright's test runner
 * already executes plain TypeScript under Node (which ships full-ICU
 * `Intl` since Node 13+), so these run as ordinary Node assertions with no
 * `page`/browser involved — see the apply-phase report for this call-out.
 */

test.describe("resolveDisplayTimezone", () => {
  test("returns the saved preference when set", () => {
    expect(resolveDisplayTimezone("Europe/Madrid")).toBe("Europe/Madrid");
  });

  test("falls back to the browser-detected timezone when preference is null", () => {
    // Stub `resolvedOptions` on a wrapper so
    // `Intl.DateTimeFormat().resolvedOptions().timeZone` returns a known
    // fixed value regardless of the machine running the test.
    const original = Intl.DateTimeFormat;
    // @ts-expect-error -- intentionally monkeypatching for this test only
    Intl.DateTimeFormat = function (...args: unknown[]) {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const instance = new (original as any)(...args);
      instance.resolvedOptions = () => ({ timeZone: "America/New_York" });
      return instance;
    };

    try {
      expect(resolveDisplayTimezone(null)).toBe("America/New_York");
    } finally {
      Intl.DateTimeFormat = original;
    }
  });

  test("falls back to UTC when preference is null and detection is unavailable", () => {
    const original = Intl.DateTimeFormat;
    // @ts-expect-error -- intentionally monkeypatching for this test only
    Intl.DateTimeFormat = function () {
      throw new Error("Intl.DateTimeFormat unavailable in this environment");
    };

    try {
      expect(resolveDisplayTimezone(null)).toBe("UTC");
      expect(resolveDisplayTimezone(undefined)).toBe("UTC");
    } finally {
      Intl.DateTimeFormat = original;
    }
  });
});

test.describe("formatInTimezone — DST-awareness", () => {
  // NOTE on locale choice: `Intl`'s `timeZoneName: 'short'` abbreviation is
  // locale-dependent CLDR data, and for many locales (including plain "en"
  // and "en-US") most IANA zones — Europe/Madrid included — resolve to a
  // generic "GMT+1"/"GMT+2" offset rather than "CET"/"CEST". `formatInTimezone`
  // defaults to "en-GB" internally (see DEFAULT_LOCALE in timezone.ts)
  // specifically so production rendering doesn't depend on the browser's
  // actual locale — these tests pass "en-GB" explicitly only to keep the
  // assertion's intent obvious at the call site.
  test("the same Europe/Madrid zone shows CET in January and CEST in July", () => {
    const januaryEntry = formatInTimezone("2026-01-15T13:00:00Z", "Europe/Madrid", "en-GB");
    const julyEntry = formatInTimezone("2026-07-15T13:00:00Z", "Europe/Madrid", "en-GB");

    expect(januaryEntry).toContain("CET");
    expect(januaryEntry).not.toContain("CEST");
    expect(julyEntry).toContain("CEST");
  });

  test("formats the date and time portion alongside the abbreviation", () => {
    // 13:00 UTC in January is 14:00 in Madrid (CET, UTC+1).
    const formatted = formatInTimezone("2026-01-15T13:00:00Z", "Europe/Madrid", "en-GB");
    expect(formatted).toBe("2026-01-15 14:00 CET");
  });

  test("defaults to a named abbreviation even when no locale is passed", () => {
    // No third argument: this is exactly how production call sites
    // (VehicleLocationHistoryModal.tsx, PreferencesPage.tsx) invoke it.
    const formatted = formatInTimezone("2026-07-15T13:00:00Z", "Europe/Madrid");
    expect(formatted).toBe("2026-07-15 15:00 CEST");
  });

  test("falls back to UTC formatting when the zone is unrecognized", () => {
    const formatted = formatInTimezone("2026-07-15T13:00:00Z", "Not/AZone");
    expect(formatted).toBe("2026-07-15 13:00 UTC");
  });
});
