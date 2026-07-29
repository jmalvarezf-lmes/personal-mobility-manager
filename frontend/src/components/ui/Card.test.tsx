import { describe, expect, it } from "vitest";

import { render, screen } from "../../test/render";
import Card from "./Card";

describe("Card", () => {
  it("renders children with the shared card styling", () => {
    render(<Card data-testid="card">content</Card>);

    const card = screen.getByTestId("card");
    expect(card).toHaveTextContent("content");
    expect(card).toHaveClass("rounded", "border", "bg-white", "shadow-sm");
  });

  it("merges a custom className with the base styling", () => {
    render(
      <Card data-testid="card" className="mt-2">
        content
      </Card>,
    );

    expect(screen.getByTestId("card")).toHaveClass("mt-2", "rounded");
  });
});
