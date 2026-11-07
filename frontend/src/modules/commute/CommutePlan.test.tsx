import { cleanup, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";
import type { CommutePlan } from "../../api/commute";
import { CommuteDetail, commuteOverview } from "./CommutePlan";

const inactive = {
  active: false,
  state: "inactive" as const,
  detail: "Pre-departure disruption checks are not active.",
};

function plan(over: Partial<CommutePlan> = {}): CommutePlan {
  return {
    summary: "Wembley Park · leave 07:22 · 34 min · Jubilee. No line disruptions.",
    shift: {
      id: "shift-1",
      start: "2026-11-07T08:00:00+00:00",
      end: "2026-11-07T16:00:00+00:00",
      location_label: "Wembley",
      when: "today",
      overnight: false,
    },
    home: { state: "configured", check: "not_verified", kind: "coordinates", label: "Home" },
    destination: { state: "configured", check: "not_verified", label: "Wembley Park", override: "default", note: null },
    arrival_buffer_minutes: 10,
    return_buffer_minutes: 0,
    outward: {
      role: "outward",
      time_is: "Arriving",
      target: "2026-11-07T07:50:00+00:00",
      clock: "07:22",
      minutes: 34,
      lines: ["Jubilee"],
      detail: "34 min · Jubilee. No line disruptions.",
      meta: "Arrive by 07:50",
      state: "planned",
    },
    back: {
      role: "return",
      time_is: "Departing",
      target: "2026-11-07T16:00:00+00:00",
      clock: "16:05",
      minutes: 36,
      lines: ["Jubilee"],
      detail: "36 min · Jubilee. No line disruptions.",
      meta: "Departs at the finish 16:00",
      state: "planned",
    },
    advisory: inactive,
    ...over,
  };
}

describe("Commute plan", () => {
  beforeEach(() => cleanup());

  it("keeps an inactive check off the urgent line", () => {
    expect(commuteOverview(plan(), null)).toEqual({
      count: "34",
      summary: "Today · Out 07:22 · back 16:05",
      urgent: null,
    });
  });

  it("says the places are configured and not verified", () => {
    render(<CommuteDetail plan={plan()} error={null} />);
    const places = document.querySelector("[data-places]")?.textContent ?? "";
    expect(places).toContain("Home is configured. Not verified with a provider.");
    expect(places).toContain("Wembley Park is configured. Not verified with a provider.");
    expect(places).not.toMatch(/\bVerified\b/);
    expect(screen.getByText("Pre-departure disruption checks are not active.")).toBeTruthy();
    expect(screen.getByText("Arrive 10 min before the start. The return departs at the finish.")).toBeTruthy();
  });

  it("names an overnight return and a future shift without calling the check active", () => {
    const overnight = plan({
      summary: "Wembley Park · 22:00–06:30. Journey check is not connected.",
      shift: {
        id: "shift-2",
        start: "2026-11-07T22:00:00+00:00",
        end: "2026-11-08T06:30:00+00:00",
        location_label: "Wembley",
        when: "overnight",
        overnight: true,
      },
      outward: {
        role: "outward",
        time_is: "Arriving",
        target: "2026-03-29T06:50:00+00:00",
        clock: null,
        minutes: null,
        lines: [],
        detail: "Journey check is not connected.",
        meta: "Arrive by 07:50",
        state: "unconnected",
      },
      back: {
        role: "return",
        time_is: "Departing",
        target: "2026-10-25T06:00:00+00:00",
        clock: null,
        minutes: null,
        lines: [],
        detail: "Journey check is not connected.",
        meta: "Departs at the finish 06:00",
        state: "unconnected",
      },
    });
    expect(commuteOverview(overnight, null).summary).toBe("Overnight · Out · back after the finish");
    render(<CommuteDetail plan={overnight} error={null} />);
    expect(screen.getByText(/29 Mar, 07:50/)).toBeTruthy();
    expect(screen.getByText(/25 Oct, 06:00/)).toBeTruthy();
    const upcoming = plan({
      shift: { ...plan().shift!, when: "upcoming", overnight: false },
    });
    expect(commuteOverview(upcoming, null).summary.startsWith("Next shift")).toBe(true);
  });

  it("shows a stale check and an error without a shift", () => {
    const stale = plan({
      advisory: {
        active: true,
        state: "stale",
        detail: "Showing the last disruption check. A newer read failed. Jubilee: Minor Delays",
      },
    });
    expect(commuteOverview(stale, null).urgent).toContain("newer read failed");
    render(<CommuteDetail plan={stale} error={null} />);
    expect(screen.getByText(/newer read failed/)).toBeTruthy();
    expect(screen.getByText(/newer read failed/).textContent?.toLowerCase()).not.toMatch(/real-?time|\blive\b/);

    cleanup();
    const empty = plan({
      summary: "No commute on the rota today.",
      shift: null,
      outward: null,
      back: null,
    });
    expect(commuteOverview(empty, null)).toEqual({
      count: "—",
      summary: "No commute on the rota today.",
      urgent: null,
    });
    render(<CommuteDetail plan={empty} error={new Error("The commute could not be read.")} />);
    expect(screen.getByRole("alert").textContent).toBe("The commute could not be read.");
  });
});
