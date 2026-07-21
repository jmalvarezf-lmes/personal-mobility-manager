import { describe, expect, it } from "vitest";

import { renderWithProviders, screen } from "../test/render";
import AmbientLabelIcon from "./AmbientLabelIcon";

describe("AmbientLabelIcon", () => {
  it("renders the sticker icon for a resolved label", () => {
    renderWithProviders(<AmbientLabelIcon label="B" />);

    const icon = screen.getByRole("img", { name: "Ambient label B" });
    expect(icon).toHaveAttribute("src", "/api/ambient-labels/B/icon");
  });

  it("renders the 'no label' indicator for category A", () => {
    renderWithProviders(<AmbientLabelIcon label="A" />);

    expect(screen.getByTestId("ambient-label-none")).toHaveTextContent("No label");
    expect(screen.queryByRole("img")).not.toBeInTheDocument();
  });

  it("renders nothing when the label is unresolved (null)", () => {
    const { container } = renderWithProviders(<AmbientLabelIcon label={null} />);

    expect(container).toBeEmptyDOMElement();
  });

  it("renders nothing when the label is unresolved (undefined)", () => {
    const { container } = renderWithProviders(<AmbientLabelIcon label={undefined} />);

    expect(container).toBeEmptyDOMElement();
  });
});
