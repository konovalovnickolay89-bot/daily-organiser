import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ReminderPreview } from "./ReminderPreview";

const getReminderPreview = vi.fn();
const prepareLocalReminders = vi.fn();
const setLocalReminders = vi.fn();
const refresh = vi.fn();

vi.mock("../../api/agent", () => ({
  getReminderPreview: () => getReminderPreview(),
  prepareLocalReminders: () => prepareLocalReminders(),
}));

vi.mock("../../api/system", () => ({
  setLocalReminders: (body: unknown) => setLocalReminders(body),
}));

vi.mock("../../house/HouseContext", () => ({
  useHouse: () => ({ tick: 0, refresh }),
}));

function preview(over: Partial<Record<string, unknown>> = {}) {
  return {
    calls_assistant: false,
    label: "Preview",
    quiet: false,
    quiet_hours: "22:00–05:59 Europe/London",
    runs_left_today: 12,
    proactive_left_today: 3,
    cap_runs: 12,
    cap_proactive: 3,
    due: null,
    held_because: null,
    candidates: [{ rule: "overdue_lingering", title: "Water the plants", reason: "Due for 5 days", type_on: false }],
    note: "Preview. Nothing is sent.",
    local_reminders: "off",
    reminder_overdue: "off",
    reminder_stalled: "off",
    reminder_upcoming: "off",
    reminder_types_ready: true,
    waiting_note: null,
    ...over,
  };
}

describe("Reminder type switches", () => {
  beforeEach(() => {
    cleanup();
    getReminderPreview.mockReset();
    prepareLocalReminders.mockReset();
    setLocalReminders.mockReset();
    refresh.mockReset();
  });

  it("shows the master and each type off, and does not prepare", async () => {
    getReminderPreview.mockResolvedValue(preview());
    render(<ReminderPreview />);
    expect((await screen.findByRole("switch", { name: "Local reminders" })) as HTMLInputElement).toHaveProperty("checked", false);
    expect(screen.getByRole("switch", { name: "Overdue tasks" })).toHaveProperty("checked", false);
    expect(screen.getByRole("switch", { name: "Stalled items" })).toHaveProperty("checked", false);
    expect(screen.getByRole("switch", { name: "Upcoming commitments" })).toHaveProperty("checked", false);
    expect(screen.getByText("Water the plants").parentElement?.textContent).toContain("This type is off.");
    expect(prepareLocalReminders).not.toHaveBeenCalled();
    for (const name of ["Overdue tasks", "Stalled items", "Upcoming commitments"]) {
      const label = screen.getByRole("switch", { name }).closest("label");
      expect(label?.className).toContain("min-h-11");
    }
  });

  it("saves one type without sending the others", async () => {
    getReminderPreview.mockResolvedValue(preview());
    setLocalReminders.mockResolvedValue({
      local_reminders: "off",
      reminder_overdue: "on",
      reminder_stalled: "off",
      reminder_upcoming: "off",
      reminder_types_ready: true,
    });
    render(<ReminderPreview />);
    fireEvent.click(await screen.findByRole("switch", { name: "Overdue tasks" }));
    await waitFor(() => expect(setLocalReminders).toHaveBeenCalledWith({ overdue: true }));
    expect(await screen.findByRole("switch", { name: "Overdue tasks" })).toHaveProperty("checked", true);
    expect(screen.getByRole("switch", { name: "Local reminders" })).toHaveProperty("checked", false);
    expect(prepareLocalReminders).not.toHaveBeenCalled();
  });

  it("keeps a waiting card visible when that type is off", async () => {
    getReminderPreview.mockResolvedValue(
      preview({
        waiting_note: "Overdue tasks are off. A reminder of that type is still waiting, so the card was left in place and no new card was prepared.",
      }),
    );
    render(<ReminderPreview />);
    const status = await screen.findByRole("status");
    expect(status.textContent).toContain("still waiting");
    expect(status.textContent).toContain("left in place");
  });

  it("shows an assessed card without calling the reply a template", async () => {
    getReminderPreview.mockResolvedValue(preview({ local_reminders: "on", reminder_overdue: "on" }));
    prepareLocalReminders.mockResolvedValue({
      prepared: 1,
      reason: "overdue_lingering",
      calls_assistant: true,
      assessment: "assessed",
      summary: "Note on Water the plants: “Have a look at this one.”",
    });
    render(<ReminderPreview />);
    expect(await screen.findByRole("status")).toHaveProperty("textContent", "Assessed. A card is waiting. Apply adds the note.");
    expect(prepareLocalReminders).toHaveBeenCalledTimes(1);
  });

  it("says when the assistant is off instead of inventing an assessment", async () => {
    getReminderPreview.mockResolvedValue(preview({ local_reminders: "on", reminder_overdue: "on" }));
    prepareLocalReminders.mockResolvedValue({
      prepared: 0,
      reason: "The assistant is off. Nothing was assessed.",
      calls_assistant: false,
      assessment: "unavailable",
      summary: null,
    });
    render(<ReminderPreview />);
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain("The assistant is off");
    expect(screen.queryByText(/Assessed/)).toBeNull();
  });

  it("does not offer a type switch before the columns exist", async () => {
    getReminderPreview.mockResolvedValue(preview({ reminder_types_ready: false }));
    render(<ReminderPreview />);
    const overdue = await screen.findByRole("switch", { name: "Overdue tasks" });
    expect(overdue).toHaveProperty("disabled", true);
    expect(screen.getByText("These types are off until the database update is applied. Nothing was turned on.")).toBeTruthy();
    fireEvent.click(overdue);
    expect(setLocalReminders).not.toHaveBeenCalled();
  });
});
