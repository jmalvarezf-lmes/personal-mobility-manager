import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { render, screen } from "../../test/render";
import Input, { inputClasses } from "./Input";

describe("Input", () => {
  it("renders a labeled text input with the shared styling", () => {
    render(
      <>
        <label htmlFor="name">Name</label>
        <Input id="name" />
      </>,
    );

    const input = screen.getByLabelText("Name");
    expect(input).toHaveClass("rounded", "border");
  });

  it("accepts user input", async () => {
    render(
      <>
        <label htmlFor="name">Name</label>
        <Input id="name" />
      </>,
    );

    await userEvent.type(screen.getByLabelText("Name"), "hello");

    expect(screen.getByLabelText("Name")).toHaveValue("hello");
  });

  it("exports its base class string for reuse by non-input elements (e.g. <select>)", () => {
    expect(inputClasses).toContain("rounded");
    expect(inputClasses).toContain("border-gray-300");
  });
});
