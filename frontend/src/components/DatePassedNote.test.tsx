import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { DatePassedNote } from "./DatePassedNote";

describe("DatePassedNote", () => {
  it("shows the note when the date has passed", () => {
    render(<DatePassedNote dueOn="2026-11-01" houseDate="2026-11-06" />);
    expect(screen.getByText("That date has passed.")).toBeTruthy();
    expect(document.querySelector("[data-note='date-passed']")).toBeTruthy();
  });

  it("renders nothing for a current date", () => {
    const { container } = render(<DatePassedNote dueOn="2026-11-06" houseDate="2026-11-06" />);
    expect(container.textContent).toBe("");
  });
});
