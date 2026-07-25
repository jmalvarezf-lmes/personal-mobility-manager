import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { getMe } from "../api/auth";
import { renderWithProviders, screen, waitFor } from "../test/render";
import ApiDocsPage from "./ApiDocsPage";

vi.mock("../api/auth");

const swaggerUiSpy = vi.fn();

vi.mock("swagger-ui-react", () => ({
  default: (props: { spec: Record<string, unknown> }) => {
    swaggerUiSpy(props);
    return <div data-testid="swagger-ui" />;
  },
}));

vi.mock("swagger-ui-react/swagger-ui.css", () => ({}));

const rawSpec = {
  openapi: "3.1.0",
  info: { title: "Personal Mobility Manager API", version: "1.0.0" },
  paths: {
    "/vehicles": {
      get: { summary: "List vehicles" },
    },
  },
};

function mockFetchOnce(body: unknown, ok = true, status = 200) {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok,
      status,
      json: () => Promise.resolve(body),
    }),
  );
}

describe("ApiDocsPage", () => {
  beforeEach(() => {
    swaggerUiSpy.mockClear();
    vi.mocked(getMe).mockResolvedValue(null);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.clearAllMocks();
  });

  it("renders without crashing and passes a spec with the injected servers entry to SwaggerUI", async () => {
    mockFetchOnce(rawSpec);

    renderWithProviders(<ApiDocsPage />, { withAuth: true, withRouter: true });

    await waitFor(() => {
      expect(screen.getByTestId("swagger-ui")).toBeInTheDocument();
    });

    expect(swaggerUiSpy).toHaveBeenCalledTimes(1);
    const passedSpec = swaggerUiSpy.mock.calls[0][0].spec;
    expect(passedSpec.servers).toEqual([{ url: "/api" }]);
    expect(passedSpec.paths).toEqual(rawSpec.paths);
  });

  it("shows an error message when the spec fails to load", async () => {
    mockFetchOnce({}, false, 500);

    renderWithProviders(<ApiDocsPage />, { withAuth: true, withRouter: true });

    await waitFor(() => {
      expect(screen.getByRole("alert")).toBeInTheDocument();
    });

    expect(swaggerUiSpy).not.toHaveBeenCalled();
  });
});
