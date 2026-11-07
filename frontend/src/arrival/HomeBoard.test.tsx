import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { HomeBoard } from "./HomeBoard";

const getMorningBrief = vi.fn();
const listTasks = vi.fn();
const getAgent = vi.fn();
const listApprovals = vi.fn();
const listXItems = vi.fn();
const getLineStatus = vi.fn();

vi.mock("../house/HouseContext", () => ({
  useHouse: () => ({ tick: 0 }),
}));

vi.mock("../api/brief", () => ({
  getMorningBrief: () => getMorningBrief(),
}));

vi.mock("../api/tasks", () => ({
  listTasks: () => listTasks(),
}));

vi.mock("../api/agent", () => ({
  getAgent: () => getAgent(),
}));

vi.mock("../api/approvals", () => ({
  listApprovals: () => listApprovals(),
}));

vi.mock("../api/x", () => ({
  listXItems: () => listXItems(),
}));

vi.mock("../api/lines", () => ({
  getLineStatus: () => getLineStatus(),
}));

vi.mock("../modules/brief/MorningBrief", () => ({
  MorningBrief: () => <h2>Morning brief</h2>,
}));

vi.mock("../modules/tasks/TodayList", () => ({
  TodayList: () => <h2>Today list</h2>,
}));

vi.mock("../modules/assistant/AssistantPane", () => ({
  AssistantPane: () => <h2>Proposed changes</h2>,
}));

vi.mock("../modules/assistant/ReasoningPane", () => ({
  ReasoningPane: () => <h2>Decisions</h2>,
}));

vi.mock("../modules/x/XCards", () => ({
  XCards: () => <p>X cards</p>,
}));

const quietLines = {
  configured: false,
  state: "missing",
  stale: false,
  fetched_at: null,
  source_at: null,
  failure: null,
  detail: "TfL is not configured.",
  lines: [],
};

describe("Home board", () => {
  beforeEach(() => {
    getLineStatus.mockReset();
    getLineStatus.mockResolvedValue(quietLines);
  });

  afterEach(() => {
    cleanup();
    window.localStorage.clear();
  });

  it("keeps an urgent line visible and remembers the open section", async () => {
    getMorningBrief.mockResolvedValue({
      sections: [
        {
          key: "tasks",
          summary: "1 overdue",
          items: [{ title: "Test data: boiler filters", meta: "Overdue · High" }],
        },
      ],
    });
    listTasks.mockResolvedValue({ items: [{ title: "Test data: bins" }] });
    getAgent.mockResolvedValue({ enabled: true, reachable: true, proposals: [{ summary: "Test data: oat milk" }] });
    listApprovals.mockResolvedValue({ items: [] });
    listXItems.mockResolvedValue({ enabled: true, items: [{ summary: "Test data: a bookmark" }] });

    render(<HomeBoard />);
    expect(screen.getByRole("heading", { name: "Morning brief" })).toBeTruthy();
    expect(await screen.findByText("Overdue: Test data: boiler filters")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: /Today/ }));
    expect(screen.getByRole("heading", { name: "Today list" })).toBeTruthy();
    expect(screen.getByText("Overdue: Test data: boiler filters")).toBeTruthy();
    expect(screen.getAllByText("Test data: oat milk").length).toBe(2);
    expect(window.localStorage.getItem("organiser-home-open")).toBe("today");

    cleanup();
    render(<HomeBoard />);
    expect(screen.getByRole("heading", { name: "Today list" })).toBeTruthy();
    const board = document.querySelector("[data-home-board]");
    expect(board?.className).toContain("minmax(0,1fr)");
    expect(board?.className).not.toContain("max-w-");
  });

  it("moves the open section from the keyboard", async () => {
    getMorningBrief.mockResolvedValue({ sections: [] });
    listTasks.mockResolvedValue({ items: [] });
    getAgent.mockResolvedValue({ enabled: true, reachable: true, proposals: [] });
    listApprovals.mockResolvedValue({ items: [] });
    listXItems.mockResolvedValue({ enabled: false, items: [] });
    render(<HomeBoard />);
    const brief = await screen.findByRole("button", { name: /Brief/ });
    brief.focus();
    fireEvent.keyDown(brief, { key: "ArrowDown" });
    await waitFor(() => expect(screen.getByRole("heading", { name: "Line status" })).toBeTruthy());
    expect(screen.getByRole("button", { name: /Lines/ }).getAttribute("aria-expanded")).toBe("true");
    fireEvent.keyDown(screen.getByRole("button", { name: /Lines/ }), { key: "ArrowDown" });
    await waitFor(() => expect(screen.getByRole("heading", { name: "Today list" })).toBeTruthy());
    expect(screen.getByRole("button", { name: /Today/ }).getAttribute("aria-expanded")).toBe("true");
  });

  it("shows a disruption on the overview with no shift and opens the lines", async () => {
    getMorningBrief.mockResolvedValue({
      sections: [{ key: "commute", summary: "Commute is not connected.", items: [] }],
    });
    listTasks.mockResolvedValue({ items: [] });
    getAgent.mockResolvedValue({ enabled: false, reachable: true, proposals: [] });
    listApprovals.mockResolvedValue({ items: [] });
    listXItems.mockResolvedValue({ enabled: false, items: [] });
    getLineStatus.mockResolvedValue({
      configured: true,
      state: "fresh",
      stale: false,
      fetched_at: "2026-11-07T14:06:00+00:00",
      source_at: "2026-11-07T14:05:00Z",
      failure: null,
      detail: null,
      lines: [
        {
          id: "jubilee",
          name: "Jubilee",
          mode: "Tube",
          severity: "Minor Delays",
          reason: "Minor delays due to a signal failure at Baker Street.",
        },
        { id: "central", name: "Central", mode: "Tube", severity: "Good Service", reason: null },
      ],
    });

    render(<HomeBoard />);
    expect(await screen.findByText("Jubilee: Minor Delays")).toBeTruthy();
    const lines = screen.getByRole("button", { name: /Lines/ });
    expect(lines.textContent).toContain("1");
    expect(lines.textContent).toContain("1 line disrupted.");
    fireEvent.click(screen.getByRole("button", { name: /Today/ }));
    expect(screen.getByText("Jubilee: Minor Delays")).toBeTruthy();
    expect(screen.queryByRole("heading", { name: "Line status" })).toBeNull();
    fireEvent.click(lines);
    expect(screen.getByRole("heading", { name: "Line status" })).toBeTruthy();
    expect(screen.getByText("Minor delays due to a signal failure at Baker Street.")).toBeTruthy();
    expect(screen.getByText(/Read at/)).toBeTruthy();
    expect(screen.getByText(/Source time/)).toBeTruthy();
    expect(getLineStatus).toHaveBeenCalledTimes(1);
  });
});
