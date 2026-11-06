import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { CatchUpCardView } from "./CatchUpStrip";

const item = {
  id: "1",
  rule: "brief",
  label: "On the brief",
  summary: "Note on Water the plants",
  reason: "Still on the brief, with no date.",
};

describe("CatchUpCardView", () => {
  it("shows the fallback marker for a brief card", () => {
    render(<CatchUpCardView item={item} busy={false} onApply={() => {}} onDismiss={() => {}} />);
    expect(screen.getByText("Fallback").getAttribute("data-marker")).toBe("fallback");
  });

  it("hides the marker for a dated card", () => {
    const view = render(
      <CatchUpCardView item={{ ...item, rule: "overdue", label: "Overdue" }} busy={false} onApply={() => {}} onDismiss={() => {}} />,
    );
    expect(view.container.querySelector("[data-marker='fallback']")).toBeNull();
  });
});
