import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { layoutPreviewQuery, LayoutPreview } from "./LayoutPreview";

describe("Layout preview", () => {
  afterEach(() => {
    cleanup();
    window.localStorage.clear();
    window.history.pushState({}, "", "/");
  });

  it("stays off the live front page", () => {
    window.history.pushState({}, "", "/");
    expect(layoutPreviewQuery()).toBe(false);
    window.history.pushState({}, "", "/?layout-preview=1");
    expect(layoutPreviewQuery()).toBe(true);
  });

  it("keeps urgent lines visible and remembers the open section", () => {
    window.localStorage.setItem("organiser-layout-preview", "x");
    render(<LayoutPreview />);
    expect(screen.getByRole("note").textContent).toContain("Not the live front page");
    expect(screen.getByRole("note").textContent).toContain("test data");
    expect(screen.getByRole("heading", { name: "X" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Connect" })).toBeTruthy();
    expect(screen.getByText("Test data: boiler filters are overdue")).toBeTruthy();
    expect(screen.getByText("Test data: oat milk is waiting")).toBeTruthy();
    expect(screen.getByRole("list", { name: "Recent activity" }).className).toContain("tube-log");

    fireEvent.click(screen.getByRole("button", { name: /Proposed changes/ }));
    expect(screen.getByRole("button", { name: "Apply" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Not now" })).toBeTruthy();
    expect(window.localStorage.getItem("organiser-layout-preview")).toBe("proposals");
    expect(screen.getByText("Test data: boiler filters are overdue")).toBeTruthy();
  });
});
