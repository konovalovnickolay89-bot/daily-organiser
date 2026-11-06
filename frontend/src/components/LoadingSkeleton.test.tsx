import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { LoadingSkeleton } from "./LoadingSkeleton";

describe("LoadingSkeleton", () => {
  it("exposes the label only to assistive tech", () => {
    render(<LoadingSkeleton label="Opening the brief…" />);
    expect(screen.getByText("Opening the brief…").className).toContain("sr-only");
  });
});
