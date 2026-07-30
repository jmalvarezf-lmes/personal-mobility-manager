/// <reference types="vitest/config" />
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";
import istanbul from "vite-plugin-istanbul";

export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
    // Instruments src/ for Istanbul-format coverage when the dev server is
    // driven by Playwright e2e tests (see e2e/fixtures/coverage.ts). Off by
    // default so normal `dev`/`build` output stays uninstrumented.
    ...(process.env.E2E_COVERAGE === "true"
      ? [istanbul({ include: "src/**/*", exclude: ["**/*.test.{ts,tsx}", "src/test/**"], extension: [".ts", ".tsx"] })]
      : []),
  ],
  server: {
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
  test: {
    environment: "jsdom",
    globals: false,
    setupFiles: ["./src/test/setup.ts"],
    include: ["src/**/*.test.{ts,tsx}"],
    coverage: {
      provider: "v8",
      reporter: ["text", "lcov"],
    },
  },
});
