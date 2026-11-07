import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { XPanel } from "./XPanel";

const getXStatus = vi.fn();
const startXConnect = vi.fn();
const disconnectX = vi.fn();
const addXWatch = vi.fn();
const removeXWatch = vi.fn();
const pauseXPoll = vi.fn();
const resumeXPoll = vi.fn();
const listXItems = vi.fn();
const pollX = vi.fn();
const assign = vi.fn();

vi.mock("../../house/HouseContext", () => ({
  useHouse: () => ({ system: { paused: false }, refresh: () => undefined }),
  useHouseTick: () => 0,
}));

vi.mock("../../api/x", () => ({
  getXStatus: () => getXStatus(),
  startXConnect: () => startXConnect(),
  disconnectX: () => disconnectX(),
  addXWatch: (kind: string, value: string) => addXWatch(kind, value),
  removeXWatch: (id: string) => removeXWatch(id),
  pauseXPoll: () => pauseXPoll(),
  resumeXPoll: () => resumeXPoll(),
  listXItems: () => listXItems(),
  pollX: () => pollX(),
  applyXItem: vi.fn(),
  dismissXItem: vi.fn(),
  postXDraft: vi.fn(),
}));

const off = {
  enabled: false,
  configured: false,
  connected: false,
  username: null,
  watches: [],
};

const disconnected = {
  enabled: true,
  configured: true,
  connected: false,
  username: null,
  watches: [],
  poll_paused: false,
  poll_interval_minutes: 30,
  last_poll_at: null,
  credits_remaining: null,
  rate_remaining: null,
  watch_limit: 20,
};

const connected = {
  ...disconnected,
  connected: true,
  username: "nickhome",
  watches: [{ id: "w1", kind: "keyword", value: "bins" }],
  last_poll_at: "2026-11-06T08:05:00+00:00",
  credits_remaining: 120,
  rate_remaining: 45,
  rate_reset_at: "2026-11-06T09:00:00+00:00",
  last_error_class: "rate",
  backing_off: true,
  backoff_until: "2026-11-06T08:20:00+00:00",
};

describe("X panel", () => {
  beforeEach(() => {
    cleanup();
    getXStatus.mockReset();
    startXConnect.mockReset();
    disconnectX.mockReset();
    addXWatch.mockReset();
    removeXWatch.mockReset();
    pauseXPoll.mockReset();
    resumeXPoll.mockReset();
    listXItems.mockReset();
    pollX.mockReset();
    assign.mockReset();
    listXItems.mockResolvedValue({ enabled: false, items: [] });
    pollX.mockResolvedValue({ ran: false, reason: "off" });
    HTMLDialogElement.prototype.showModal = function showModal() {
      this.setAttribute("open", "");
    };
    HTMLDialogElement.prototype.close = function close() {
      this.removeAttribute("open");
    };
    vi.stubGlobal("location", { assign, search: "", pathname: "/", href: "http://localhost/" });
  });

  it("shows X off with the controls disabled", async () => {
    getXStatus.mockResolvedValue(off);
    render(<XPanel />);
    expect(await screen.findByText(/The house file has to turn it on/)).toBeTruthy();
    expect((screen.getByRole("button", { name: "Connect" }) as HTMLButtonElement).disabled).toBe(true);
    expect((screen.getByRole("button", { name: "Pause reading" }) as HTMLButtonElement).disabled).toBe(true);
    expect(screen.queryByText(/does not set a spend cap/)).toBeNull();
  });

  it("keeps Connect closed when the house file has no app", async () => {
    getXStatus.mockResolvedValue({ ...disconnected, configured: false });
    render(<XPanel />);
    expect(await screen.findByText(/does not take a key/)).toBeTruthy();
    expect((screen.getByRole("button", { name: "Connect" }) as HTMLButtonElement).disabled).toBe(true);
    expect(startXConnect).not.toHaveBeenCalled();
  });

  it("opens X only after Connect is confirmed, and does not show the address", async () => {
    getXStatus.mockResolvedValue(disconnected);
    const url = "https://twitter.com/i/oauth2/authorize?state=secret-state&code_challenge=secret-challenge";
    startXConnect.mockResolvedValue({ authorize_url: url });
    render(<XPanel />);
    fireEvent.click(await screen.findByRole("button", { name: "Connect" }));
    expect(startXConnect).not.toHaveBeenCalled();
    expect(screen.getByRole("heading", { name: "Open X to connect?" })).toBeTruthy();
    fireEvent.click(screen.getByRole("dialog").querySelector("button") as HTMLButtonElement);
    await waitFor(() => expect(startXConnect).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(assign).toHaveBeenCalledWith(url));
    expect(screen.queryByText(/secret-state/)).toBeNull();
    expect(screen.queryByText(/secret-challenge/)).toBeNull();
  });

  it("pauses reading, refuses a bad watch, and cancels disconnect", async () => {
    getXStatus.mockResolvedValue(connected);
    pauseXPoll.mockResolvedValue({ ...connected, poll_paused: true });
    render(<XPanel />);
    expect(await screen.findByText(/Connected as/)).toBeTruthy();
    expect(screen.getByText("@nickhome")).toBeTruthy();
    expect(screen.getByText("X reported a rate limit. Reading waits.")).toBeTruthy();
    expect(screen.getByText("120")).toBeTruthy();
    expect(screen.getByText(/does not set a spend cap/)).toBeTruthy();
    expect(screen.queryByText(/\$/)).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "Pause reading" }));
    await waitFor(() => expect(pauseXPoll).toHaveBeenCalledTimes(1));
    expect(await screen.findByRole("button", { name: "Resume reading" })).toBeTruthy();

    fireEvent.change(screen.getByLabelText("Watch"), { target: { value: "bins!" } });
    expect(screen.getByText(/plain words/)).toBeTruthy();
    expect((screen.getByRole("button", { name: "Add" }) as HTMLButtonElement).disabled).toBe(true);
    expect(addXWatch).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: "Disconnect" }));
    expect(screen.getByRole("heading", { name: "Disconnect X?" })).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(disconnectX).not.toHaveBeenCalled();
  });

  it("shows a load error and does not invent a connection", async () => {
    getXStatus.mockRejectedValue(new Error("The house log is not reachable."));
    render(<XPanel />);
    expect(await screen.findByRole("alert")).toHaveProperty("textContent", "The house log is not reachable.");
    expect(screen.queryByRole("button", { name: "Connect" })).toBeNull();
    expect(screen.queryByText(/Connected as/)).toBeNull();
  });
});
