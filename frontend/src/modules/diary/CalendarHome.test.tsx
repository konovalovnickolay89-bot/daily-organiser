import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import type { BriefSection } from "../../api/brief";
import { CalendarDetail, calendarOverview } from "./CalendarHome";

const today: BriefSection = {
  key: "appointments",
  title: "Appointments",
  summary: "1 appointment",
  footnote: "Read only. This is not a calendar.",
  items: [{ title: "Test data: put the bins out", meta: "09:30", ref: "fixturebins" }],
};

const emptyDay: BriefSection = {
  key: "appointments",
  title: "Appointments",
  summary: "Nothing on the diary today.",
  footnote: "Read only. This is not a calendar.",
  items: [],
};

const unavailable: BriefSection = {
  key: "appointments",
  title: "Appointments",
  summary: "Diary not connected — reconnect in Settings.",
  footnote: "Read only. This is not a calendar.",
  items: [],
};

describe("Calendar home", () => {
  afterEach(() => cleanup());

  it("counts today's fixture and keeps the title on the row", () => {
    expect(calendarOverview(today, null)).toEqual({
      count: "1",
      summary: "1 appointment",
      urgent: "Test data: put the bins out",
    });
    render(<CalendarDetail section={today} error={null} />);
    expect(screen.getByRole("heading", { name: "Calendar" })).toBeTruthy();
    expect(screen.getByText("Today only. Read only. This is not a calendar.")).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Test data: put the bins out" })).toBeTruthy();
    expect(screen.getByText("09:30")).toBeTruthy();
  });

  it("shows an empty day as zero, not as a failed read", () => {
    expect(calendarOverview(emptyDay, null)).toEqual({
      count: "0",
      summary: "Nothing on the diary today.",
      urgent: null,
    });
    render(<CalendarDetail section={emptyDay} error={null} />);
    expect(screen.getAllByText("Nothing on the diary today.").length).toBeGreaterThan(0);
    expect(screen.queryByRole("heading", { name: "Test data: put the bins out" })).toBeNull();
  });

  it("uses the brief sentence when the diary read did not return events", () => {
    expect(calendarOverview(unavailable, null)).toEqual({
      count: "—",
      summary: "Diary not connected — reconnect in Settings.",
      urgent: null,
    });
  });

  it("reports a failed brief without a health status", () => {
    const error = new Error("The brief did not answer.");
    expect(calendarOverview(null, error)).toEqual({
      count: "—",
      summary: "The diary could not be read.",
      urgent: "The brief did not answer.",
    });
    render(<CalendarDetail section={null} error={error} />);
    expect(screen.getByRole("alert").textContent).toBe("The brief did not answer.");
    expect(screen.queryByText(/last check/i)).toBeNull();
  });
});
