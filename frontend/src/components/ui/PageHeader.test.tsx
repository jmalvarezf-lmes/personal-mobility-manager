import { describe, expect, it } from "vitest";

import { render, screen } from "../../test/render";
import PageHeader from "./PageHeader";

describe("PageHeader", () => {
  it("renders the title as a heading", () => {
    render(<PageHeader title="My Vehicles" />);

    expect(screen.getByRole("heading", { name: "My Vehicles" })).toBeInTheDocument();
  });

  it("renders an optional action slot", () => {
    render(<PageHeader title="My Vehicles" action={<button>Add</button>} />);

    expect(screen.getByRole("button", { name: "Add" })).toBeInTheDocument();
  });

  it("omits the action slot when none is provided", () => {
    render(<PageHeader title="My Vehicles" />);

    expect(screen.getByRole("heading").parentElement?.children).toHaveLength(1);
  });
});
