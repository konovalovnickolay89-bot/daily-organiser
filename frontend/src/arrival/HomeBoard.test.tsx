import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { HomeBoard } from "./HomeBoard";

const getMorningBrief = vi.fn();
const listTasks = vi.fn();
const getAgent = vi.fn();
const listApprovals = vi.fn();
const listXItems = vi.fn();

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

describe("Home board", () => {
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
    await waitFor(() => expect(screen.getByRole("heading", { name: "Today list" })).toBeTruthy());
    expect(screen.getByRole("button", { name: /Today/ }).getAttribute("aria-expanded")).toBe("true");
  });
});
