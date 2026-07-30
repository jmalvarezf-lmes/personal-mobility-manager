import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { getMe } from "../api/auth";
import { renderWithProviders, screen } from "../test/render";
import LandingPage from "./LandingPage";

vi.mock("../api/auth");

describe("LandingPage", () => {
  beforeEach(() => {
    vi.mocked(getMe).mockResolvedValue(null);
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it("renders the hero headline and subtitle", () => {
    renderWithProviders(<LandingPage />, { withAuth: true, withRouter: true });

    expect(
      screen.getByRole("heading", {
        level: 1,
        name: "Track, park, and get notified — all your mobility, one place",
      }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Personal Mobility Manager keeps tabs on your vehicles/i),
    ).toBeInTheDocument();
  });

  it("links the Google login button to the OAuth entry point", () => {
    renderWithProviders(<LandingPage />, { withAuth: true, withRouter: true });

    const loginLinks = screen.getAllByRole("link", { name: "Login with Google" });
    expect(loginLinks[0]).toHaveAttribute("href", "/api/auth/google/login");
  });

  it("renders the three feature cards", () => {
    renderWithProviders(<LandingPage />, { withAuth: true, withRouter: true });

    expect(screen.getByRole("heading", { name: "Track" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Park" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Notify" })).toBeInTheDocument();
  });

  it("links the cities CTA to the map", () => {
    renderWithProviders(<LandingPage />, { withAuth: true, withRouter: true });

    const cta = screen.getByRole("link", { name: "See supported cities" });
    expect(cta).toHaveAttribute("href", "/map");
  });

  it("links the open-source CTA to the GitHub repository", () => {
    renderWithProviders(<LandingPage />, { withAuth: true, withRouter: true });

    const cta = screen.getByRole("link", { name: /View source on GitHub/i });
    expect(cta).toHaveAttribute(
      "href",
      "https://github.com/jmalvarezf-lmes/personal-mobility-manager",
    );
    expect(cta).toHaveAttribute("target", "_blank");
  });
});
