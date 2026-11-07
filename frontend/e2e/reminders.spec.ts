import { expect, test } from "@playwright/test";

const NAMES = ["Local reminders", "Overdue tasks", "Stalled items", "Upcoming commitments"] as const;

async function openReminders(page: import("@playwright/test").Page) {
  await page.goto("/");
  await page.getByRole("button", { name: "Decisions" }).click();
  await expect(page.getByRole("heading", { name: "Reminder preview" })).toBeVisible();
}

test.afterEach(async ({ request }) => {
  await request.post("/system/local-reminders", { data: { enabled: false, overdue: false, stalled: false, upcoming: false } });
});

test("reminder switches stay off and a type can be saved on its own", async ({ page, request }) => {
  await request.post("/system/local-reminders", { data: { enabled: false, overdue: false, stalled: false, upcoming: false } });
  await openReminders(page);
  for (const name of NAMES) {
    const toggle = page.getByRole("switch", { name });
    await expect(toggle).toBeVisible();
    await expect(toggle).not.toBeChecked();
    const box = await toggle.locator("xpath=..").boundingBox();
    expect(box && box.height >= 44).toBeTruthy();
  }

  await page.getByRole("switch", { name: "Overdue tasks" }).click();
  await expect(page.getByRole("switch", { name: "Overdue tasks" })).toBeChecked();
  await expect(page.getByRole("switch", { name: "Local reminders" })).not.toBeChecked();
  await expect(page.getByRole("switch", { name: "Stalled items" })).not.toBeChecked();

  await page.reload();
  await page.getByRole("button", { name: "Decisions" }).click();
  await expect(page.getByRole("switch", { name: "Overdue tasks" })).toBeChecked();
  await expect(page.getByRole("switch", { name: "Local reminders" })).not.toBeChecked();

  const oldClient = await request.post("/system/local-reminders", { data: { enabled: false } });
  expect(oldClient.ok()).toBeTruthy();
  const facts = await oldClient.json();
  expect(facts.local_reminders).toBe("off");
  expect(facts.reminder_overdue).toBe("on");
  expect(facts.reminder_stalled).toBe("off");
  expect(facts.reminder_upcoming).toBe("off");
});

const preview = {
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
  candidates: [{ rule: "overdue_lingering", title: "Water the plants", reason: "5 days overdue", type_on: true }],
  note: "Rules list the lines. A card is added only after an assessment.",
  local_reminders: "on",
  reminder_overdue: "on",
  reminder_stalled: "off",
  reminder_upcoming: "off",
  reminder_types_ready: true,
  waiting_note: null,
};

async function mockAssessment(page: import("@playwright/test").Page, result: Record<string, unknown>) {
  await page.route("**/agent/preview", (route) => route.fulfill({ json: preview }));
  await page.route("**/agent/reminders", (route) => route.fulfill({ json: result }));
}

test("an assessed reminder is labelled as assessed", async ({ page }) => {
  await mockAssessment(page, {
    prepared: 1,
    reason: "overdue_lingering",
    calls_assistant: true,
    assessment: "assessed",
    summary: "Note on Water the plants: “Have a look at this one.”",
  });
  await openReminders(page);
  await expect(page.getByRole("status").filter({ hasText: "Assessed. A card is waiting." })).toBeVisible();
  await expect(page.getByText("Rules list the lines. A card is added only after an assessment.")).toBeVisible();
});

test("an unavailable assessment is not labelled as assessed", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await mockAssessment(page, {
    prepared: 0,
    reason: "The assistant is off. Nothing was assessed.",
    calls_assistant: false,
    assessment: "unavailable",
    summary: null,
  });
  await openReminders(page);
  await expect(page.getByRole("alert")).toContainText("The assistant is off");
  await expect(page.getByText("Assessed. A card is waiting.")).toHaveCount(0);
});

test("reminder switches fit a narrow screen", async ({ page, request }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await request.post("/system/local-reminders", { data: { enabled: false, overdue: false, stalled: false, upcoming: false } });
  await openReminders(page);
  for (const name of NAMES) {
    const toggle = page.getByRole("switch", { name });
    await expect(toggle).toBeVisible();
    const box = await toggle.locator("xpath=..").boundingBox();
    expect(box && box.height >= 44).toBeTruthy();
    expect(box && box.width >= 44).toBeTruthy();
  }
});
