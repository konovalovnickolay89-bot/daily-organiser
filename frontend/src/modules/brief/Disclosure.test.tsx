import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Disclosure } from "./Disclosure";

describe("Disclosure", () => {
  it("starts open when asked and keeps a 44px summary", () => {
    render(
      <Disclosure startOpen summary={<span>Tasks</span>}>
        <p>Put the bins out</p>
      </Disclosure>,
    );
    const summary = screen.getByText("Tasks").closest("summary");
    expect(summary?.className).toContain("min-h-11");
    expect(screen.getByText("Put the bins out")).toBeTruthy();
    expect((summary?.parentElement as HTMLDetailsElement).open).toBe(true);
  });
});
