import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Rail } from "./Rail";

describe("Rail", () => {
  it("keeps a screen-reader label and a title on every control", () => {
    render(<Rail view="home" onView={() => {}} />);
    for (const label of ["Home", "Brief", "Tasks", "Approvals", "Today", "Settings"]) {
      const button = screen.getByRole("button", { name: label });
      expect(button.getAttribute("title")).toBe(label);
      expect(button.className).toContain("h-11");
      expect(button.className).toContain("w-11");
    }
    expect(screen.getByRole("button", { name: "Home" }).getAttribute("aria-current")).toBe("page");
  });
});
