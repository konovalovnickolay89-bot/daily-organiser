import { cleanup, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ViewProvider } from "./view";
import { ThemeCard } from "./ThemeCard";

const api = vi.hoisted(() => ({
  diary: "not configured" as "configured" | "not configured",
  listCalendars: vi.fn(),
}));

vi.mock("../house/HouseContext", () => ({
  useHouse: () => ({ tick: 1, refresh: () => {} }),
  useHouseTick: () => 1,
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
      diary: api.diary,
      weather_location: "not configured",
      tfl: "configured",
      banto: "not configured",
      voice_input: "off",
    }),
  setAssistantSwitch: vi.fn(),
  listCalendars: () => api.listCalendars(),
  addCalendar: vi.fn(),
  removeCalendar: vi.fn(),
}));

describe("Settings journey status", () => {
  beforeEach(() => {
    cleanup();
    api.diary = "not configured";
    api.listCalendars.mockReset();
  });

  it("keeps the TfL key fact and leaves operational line status off this card", async () => {
    render(
      <ViewProvider view="settings">
        <ThemeCard choice="auto" onChoose={() => {}} />
      </ViewProvider>,
    );
    expect(await screen.findByText("Configured")).toBeTruthy();
    const tfl = screen.getByText("TfL");
    expect(tfl.closest(".fact-row")?.querySelector("dd")?.textContent).toBe("Configured");
    expect(screen.queryByRole("heading", { name: "Line status" })).toBeNull();
    expect(screen.queryByText(/Jubilee/)).toBeNull();
    expect(screen.queryByText(/journey source is not connected/i)).toBeNull();
    const checks = screen.getByText("Disruption checks");
    expect(checks.closest(".fact-row")?.querySelector("dd")?.textContent).toBe("Not active");
    expect(screen.getByText(/Pre-departure disruption checks stay off/)).toBeTruthy();
    expect(screen.queryByText(/does not create an event/)).toBeNull();
  });

  it("says adding a calendar name does not create an event", async () => {
    api.diary = "configured";
    api.listCalendars.mockResolvedValue({ configured: true, using_primary: true, items: [] });
    render(
      <ViewProvider view="settings">
        <ThemeCard choice="auto" onChoose={() => {}} />
      </ViewProvider>,
    );
    expect(await screen.findByText("Using the primary calendar.")).toBeTruthy();
    expect(screen.getByText("Adds a calendar to read, by its name. This does not create an event.")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Add" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: /create event/i })).toBeNull();
    expect(screen.getByLabelText("Calendar to read")).toBeTruthy();
  });
});
