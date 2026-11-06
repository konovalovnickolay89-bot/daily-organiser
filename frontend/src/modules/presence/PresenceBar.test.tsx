import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { PresenceBar } from "./PresenceBar";

vi.mock("../../house/HouseContext", () => ({
  useHouse: () => ({
    system: {
      paused: false,
      greeting: "Good morning",
      house_date: "2026-11-06",
      status_text: "All quiet",
      greeting_reason: "time_of_day",
    },
    error: null,
    busy: false,
    togglePause: () => {},
  }),
}));

describe("PresenceBar", () => {
  it("shows the greeting and a 44px pause control", () => {
    render(<PresenceBar />);
    expect(screen.getByRole("heading", { name: "Good morning" })).toBeTruthy();
    const pause = screen.getByRole("button", { name: "Pause the house" });
    expect(pause.className).toContain("min-h-11");
    expect(pause.className).toContain("min-w-11");
  });
});
