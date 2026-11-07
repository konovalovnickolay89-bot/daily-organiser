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
