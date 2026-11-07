import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ViewProvider } from "../../arrival/view";
import type { LineStatus } from "../../api/lines";
import { formatHouseTime } from "../status/format";
import { LineStatusPanel } from "./LineStatusPanel";

const getLineStatus = vi.fn();

vi.mock("../../api/lines", () => ({
  getLineStatus: () => getLineStatus(),
}));

const fresh: LineStatus = {
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
    {
      id: "central",
      name: "Central",
      mode: "Tube",
      severity: "Good Service",
      reason: null,
    },
  ],
};

function renderAt(view: string) {
  return render(
    <ViewProvider view={view}>
      <LineStatusPanel />
    </ViewProvider>,
  );
}

describe("Line status", () => {
  beforeEach(() => {
    cleanup();
    getLineStatus.mockReset();
  });

  it("does not fetch until Settings is open", async () => {
    getLineStatus.mockResolvedValue(fresh);
    const view = renderAt("home");
    expect(screen.queryByRole("heading", { name: "Line status" })).toBeNull();
    expect(getLineStatus).not.toHaveBeenCalled();
    view.rerender(
      <ViewProvider view="settings">
        <LineStatusPanel />
      </ViewProvider>,
    );
    expect(await screen.findByRole("heading", { name: "Line status" })).toBeTruthy();
    expect(getLineStatus).toHaveBeenCalledTimes(1);
  });

  it("shows each line, the disruption, and both times", async () => {
    getLineStatus.mockResolvedValue(fresh);
    renderAt("settings");
    expect(await screen.findByRole("heading", { name: "Jubilee" })).toBeTruthy();
    expect(screen.getByText("Minor delays due to a signal failure at Baker Street.")).toBeTruthy();
    expect(screen.getByText("Minor Delays")).toBeTruthy();
    expect(screen.getByText("Good Service")).toBeTruthy();
    const central = document.querySelector("[data-line='central']");
    expect(central?.querySelector("[data-reason]")).toBeNull();
    const readout = document.querySelector("[data-readout]")?.textContent ?? "";
    expect(readout).toContain(`Read at ${formatHouseTime(fresh.fetched_at)}.`);
    expect(readout).toContain(`Source time ${formatHouseTime(fresh.source_at)}.`);
    expect(readout.toLowerCase()).not.toMatch(/real-?time|\blive\b/);
    expect(screen.queryByText(/journey source is not connected/i)).toBeNull();
  });

  it("says the key is missing without blaming the upstream", async () => {
    getLineStatus.mockResolvedValue({
      configured: false,
      state: "missing",
      stale: false,
      fetched_at: null,
      source_at: null,
      failure: null,
      detail: "TfL is not configured.",
      lines: [],
    });
    renderAt("settings");
    expect(await screen.findByText("TfL is not configured.")).toBeTruthy();
    expect(screen.queryByText("Jubilee")).toBeNull();
  });

  it("keeps a configured key distinct from an upstream refusal", async () => {
    getLineStatus.mockResolvedValue({
      configured: true,
      state: "error",
      stale: false,
      fetched_at: null,
      source_at: null,
      failure: "refused",
      detail: "TfL refused the line status.",
      lines: [],
    });
    renderAt("settings");
    expect(await screen.findByText("TfL refused the line status.")).toBeTruthy();
    expect(screen.queryByText(/not configured/i)).toBeNull();
    expect(document.querySelector("[data-state='error']")).toBeTruthy();
  });

  it("labels a stale read without calling it live", async () => {
    getLineStatus.mockResolvedValue({
      ...fresh,
      state: "stale",
      stale: true,
      failure: "timeout",
      detail: "Showing the last line status. A newer read failed. TfL did not answer in time.",
    });
    renderAt("settings");
    const readout = (await screen.findByText(/newer read failed/)).textContent ?? "";
    expect(readout).toContain("TfL did not answer in time.");
    expect(readout).toContain(`Read at ${formatHouseTime(fresh.fetched_at)}.`);
    expect(readout.toLowerCase()).not.toMatch(/real-?time|\blive\b/);
    expect(screen.getByText("Jubilee")).toBeTruthy();
  });

  it("shows a house error when the read cannot be asked for", async () => {
    getLineStatus.mockRejectedValue(new Error("The house log is not reachable."));
    renderAt("settings");
    expect(await screen.findByRole("alert")).toHaveProperty("textContent", "The house log is not reachable.");
    await waitFor(() => expect(getLineStatus).toHaveBeenCalledTimes(1));
  });
});
