import { randomUUID } from "node:crypto";
import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";

import { test as base } from "@playwright/test";

const COVERAGE_DIR = path.resolve(import.meta.dirname, "../../.nyc_output");

/**
 * Extends `test` so that, when E2E_COVERAGE=true (see vite.config.ts), the
 * page's Istanbul coverage map is dumped to .nyc_output/ after each test.
 * All other e2e fixtures (e.g. ./auth) build on top of this one so every
 * spec picks up coverage collection regardless of which fixture it imports.
 */
export const test = base.extend({
  page: async ({ page }, use) => {
    await use(page);

    if (process.env.E2E_COVERAGE !== "true") return;

    const coverage = await page
      .evaluate(() => (window as unknown as { __coverage__?: unknown }).__coverage__)
      .catch(() => undefined);
    if (!coverage) return;

    await mkdir(COVERAGE_DIR, { recursive: true });
    await writeFile(path.join(COVERAGE_DIR, `${randomUUID()}.json`), JSON.stringify(coverage));
  },
});

export { expect } from "@playwright/test";
