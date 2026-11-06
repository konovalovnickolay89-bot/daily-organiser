import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { TaskRow } from "./TaskRow";

describe("TaskRow", () => {
  it("names the row from the title and the meta", () => {
    render(<TaskRow title="Put the bins out" meta="Due today · High · To do" onOpen={() => {}} />);
    const button = screen.getByRole("button", { name: "Open Put the bins out. Due today · High · To do" });
    expect(button.className).toContain("min-h-11");
  });
});
