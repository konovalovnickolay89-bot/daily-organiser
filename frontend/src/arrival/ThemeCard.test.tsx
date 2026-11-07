import { cleanup, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ViewProvider } from "./view";
import { ThemeCard } from "./ThemeCard";

vi.mock("../house/HouseContext", () => ({
  useHouse: () => ({ tick: 1, refresh: () => {} }),
  useHouseTick: () => 1,
}));

vi.mock("../modules/lines/LineStatusPanel", () => ({
  LineStatusPanel: () => <p>Jubilee Minor Delays</p>,
}));

vi.mock("../modules/status/StatusPanel", () => ({
  StatusPanel: () => <h3>Status</h3>,
}));

vi.mock("../modules/x/XSettings", () => ({
  XSettings: () => null,
}));

vi.mock("../modules/memory/MemoryScreen", () => ({
  MemoryScreen: () => null,
}));

vi.mock("../api/system", () => ({
  getHouseFacts: () =>
    Promise.resolve({
      timezone: "Europe/London",
      assistant: "off",
      assistant_switch: "off",
      runs_left_today: 12,
      diary: "not configured",
      weather_location: "not configured",
      tfl: "configured",
      banto: "not configured",
      voice_input: "off",
    }),
  setAssistantSwitch: vi.fn(),
  listCalendars: vi.fn(),
  addCalendar: vi.fn(),
  removeCalendar: vi.fn(),
}));

describe("Settings journey status", () => {
  beforeEach(() => cleanup());

  it("shows the key as configured and the line read in place of a fixed disconnected line", async () => {
    render(
      <ViewProvider view="settings">
        <ThemeCard choice="auto" onChoose={() => {}} />
      </ViewProvider>,
    );
    expect(await screen.findByText("Configured")).toBeTruthy();
    const tfl = screen.getByText("TfL");
    expect(tfl.closest(".fact-row")?.querySelector("dd")?.textContent).toBe("Configured");
    expect(screen.getByText("Jubilee Minor Delays")).toBeTruthy();
    expect(screen.getByText(/The diary is read-only/)).toBeTruthy();
    expect(screen.queryByText(/journey source is not connected/i)).toBeNull();
  });
});
