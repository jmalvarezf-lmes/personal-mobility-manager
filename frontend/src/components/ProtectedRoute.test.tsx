import { Route, Routes } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { getMe } from "../api/auth";
import { renderWithProviders, screen } from "../test/render";
import ProtectedRoute from "./ProtectedRoute";

vi.mock("../api/auth");

function renderProtected() {
  return renderWithProviders(
    <Routes>
      <Route path="/" element={<div>Landing page</div>} />
      <Route
        path="/protected"
        element={
          <ProtectedRoute>
            <div>Protected content</div>
          </ProtectedRoute>
        }
      />
    </Routes>,
    { withAuth: true, withRouter: true, initialEntries: ["/protected"] },
  );
}

describe("ProtectedRoute", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("renders nothing while auth is loading", () => {
    vi.mocked(getMe).mockReturnValue(new Promise(() => {}));
    renderProtected();

    expect(screen.queryByText("Protected content")).not.toBeInTheDocument();
    expect(screen.queryByText("Landing page")).not.toBeInTheDocument();
  });

  it("redirects to / when there is no authenticated user", async () => {
    vi.mocked(getMe).mockResolvedValue(null);
    renderProtected();

    expect(await screen.findByText("Landing page")).toBeInTheDocument();
    expect(screen.queryByText("Protected content")).not.toBeInTheDocument();
  });

  it("renders the children when the user is authenticated", async () => {
    vi.mocked(getMe).mockResolvedValue({
      id: "u1",
      email: "user@example.com",
      display_name: "User",
    });
    renderProtected();

    expect(await screen.findByText("Protected content")).toBeInTheDocument();
    expect(screen.queryByText("Landing page")).not.toBeInTheDocument();
  });
});
