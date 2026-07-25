import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { getMe } from "../api/auth";
import { renderWithProviders, screen } from "../test/render";
import Nav from "./Nav";

vi.mock("../api/auth");

describe("Nav", () => {
  beforeEach(() => {
    vi.mocked(getMe).mockResolvedValue(null);
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it("shows the API docs link with no authenticated user, and it requires no login to click", async () => {
    renderWithProviders(<Nav />, { withAuth: true, withRouter: true });

    const link = await screen.findByRole("link", { name: "API Docs" });
    expect(link).toHaveAttribute("href", "/api-docs");
  });
});
