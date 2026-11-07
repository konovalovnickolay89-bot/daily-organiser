import { cleanup, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";
import type { LineStatus } from "../../api/lines";
import { formatHouseTime } from "../status/format";
import { LineStatusDetail, lineOverview } from "./LineStatusPanel";

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

describe("Line status", () => {
  beforeEach(() => cleanup());

  it("counts disruptions for the Home row and keeps a good line quiet", () => {
    expect(lineOverview(fresh, null)).toEqual({
      count: "1",
      summary: "1 line disrupted.",
      urgent: "Jubilee: Minor Delays",
    });
  });

  it("shows each line, the disruption, and both times", () => {
    render(<LineStatusDetail status={fresh} error={null} />);
    expect(screen.getByRole("heading", { name: "Line status" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Jubilee" })).toBeTruthy();
    expect(screen.getByText("Minor delays due to a signal failure at Baker Street.")).toBeTruthy();
    expect(screen.getByText("Minor Delays")).toBeTruthy();
    expect(screen.getByText("Good Service")).toBeTruthy();
    const central = document.querySelector("[data-line='central']");
    expect(central?.querySelector("[data-reason]")).toBeNull();
    const readout = document.querySelector("[data-readout]")?.textContent ?? "";
    expect(readout).toContain(`Read at ${formatHouseTime(fresh.fetched_at)}.`);
    expect(readout).toContain(`Source time ${formatHouseTime(fresh.source_at)}.`);
    expect(readout.toLowerCase()).not.toMatch(/real-?time|\blive\b/);
  });

  it("says the key is missing without blaming the upstream", () => {
    const missing: LineStatus = {
      configured: false,
      state: "missing",
      stale: false,
      fetched_at: null,
      source_at: null,
      failure: null,
      detail: "TfL is not configured.",
      lines: [],
    };
    expect(lineOverview(missing, null).summary).toBe("TfL is not configured.");
    expect(lineOverview(missing, null).urgent).toBeNull();
    render(<LineStatusDetail status={missing} error={null} />);
    expect(screen.getByText("TfL is not configured.")).toBeTruthy();
    expect(screen.queryByText("Jubilee")).toBeNull();
  });

  it("keeps a configured key distinct from an upstream refusal", () => {
    const refused: LineStatus = {
      configured: true,
      state: "error",
      stale: false,
      fetched_at: null,
      source_at: null,
      failure: "refused",
      detail: "TfL refused the line status.",
      lines: [],
    };
    const row = lineOverview(refused, null);
    expect(row.count).toBe("—");
    expect(row.urgent).toBe("TfL refused the line status.");
    render(<LineStatusDetail status={refused} error={null} />);
    expect(screen.getByText("TfL refused the line status.")).toBeTruthy();
    expect(screen.queryByText(/not configured/i)).toBeNull();
    expect(document.querySelector("[data-state='error']")).toBeTruthy();
  });

  it("labels a stale read without calling it live", () => {
    const stale: LineStatus = {
      ...fresh,
      state: "stale",
      stale: true,
      failure: "timeout",
      detail: "Showing the last line status. A newer read failed. TfL did not answer in time.",
    };
    expect(lineOverview(stale, null).urgent).toBe("A newer read failed. Jubilee: Minor Delays");
    render(<LineStatusDetail status={stale} error={null} />);
    const readout = screen.getByText(/newer read failed/).textContent ?? "";
    expect(readout).toContain("TfL did not answer in time.");
    expect(readout).toContain(`Read at ${formatHouseTime(fresh.fetched_at)}.`);
    expect(readout.toLowerCase()).not.toMatch(/real-?time|\blive\b/);
    expect(screen.getByText("Jubilee")).toBeTruthy();
  });
});
