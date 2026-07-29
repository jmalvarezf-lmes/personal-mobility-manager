import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { render, screen } from "../../test/render";
import Button from "./Button";

describe("Button", () => {
  it("renders the primary variant using the brand color token", () => {
    render(<Button variant="primary">Save</Button>);

    expect(screen.getByRole("button", { name: "Save" })).toHaveClass("bg-brand-blue");
  });

  it("renders the secondary variant with a neutral background distinct from primary", () => {
    render(<Button variant="secondary">Cancel</Button>);

    const button = screen.getByRole("button", { name: "Cancel" });
    expect(button).toHaveClass("bg-gray-100");
    expect(button).not.toHaveClass("bg-brand-blue");
  });

  it("defaults to type=button so it never accidentally submits a form", () => {
    render(<Button>Click</Button>);

    expect(screen.getByRole("button", { name: "Click" })).toHaveAttribute("type", "button");
  });

  it("calls onClick when clicked", async () => {
    const onClick = vi.fn();
    render(<Button onClick={onClick}>Click</Button>);

    await userEvent.click(screen.getByRole("button", { name: "Click" }));

    expect(onClick).toHaveBeenCalledTimes(1);
  });

  it("renders as an anchor when as='a', preserving href", () => {
    render(
      <Button as="a" href="/api/auth/google/login">
        Login
      </Button>,
    );

    const link = screen.getByRole("link", { name: "Login" });
    expect(link).toHaveAttribute("href", "/api/auth/google/login");
  });
});
