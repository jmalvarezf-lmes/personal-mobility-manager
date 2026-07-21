import { render, type RenderOptions, type RenderResult } from "@testing-library/react";
import type { ReactElement } from "react";
import { I18nextProvider } from "react-i18next";
import { MemoryRouter } from "react-router-dom";

import { AuthProvider } from "../context/AuthContext";
import testI18n from "./i18n";

interface RenderWithProvidersOptions extends RenderOptions {
  /** Wrap with `AuthProvider` — needed by components that call `useAuth()`, directly or via a child like `Nav`. Defaults to `false`. */
  withAuth?: boolean;
  /** Wrap with `MemoryRouter` — needed by components using router hooks/links. Defaults to `false`. */
  withRouter?: boolean;
  /** Initial entries passed to `MemoryRouter` when `withRouter` is `true`. */
  initialEntries?: string[];
}

/**
 * Render helper for component tests: always wraps `ui` with the test
 * `I18nextProvider` (real English strings, no network calls), and
 * optionally with `AuthProvider` and/or `MemoryRouter` based on what the
 * component under test needs.
 */
export function renderWithProviders(
  ui: ReactElement,
  options: RenderWithProvidersOptions = {},
): RenderResult {
  const { withAuth = false, withRouter = false, initialEntries, ...renderOptions } = options;

  let content = ui;

  if (withAuth) {
    content = <AuthProvider>{content}</AuthProvider>;
  }

  if (withRouter) {
    content = <MemoryRouter initialEntries={initialEntries}>{content}</MemoryRouter>;
  }

  content = <I18nextProvider i18n={testI18n}>{content}</I18nextProvider>;

  return render(content, renderOptions);
}

export * from "@testing-library/react";
