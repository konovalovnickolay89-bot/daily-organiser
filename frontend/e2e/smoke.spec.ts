import { expect, test } from "@playwright/test";

test("skip link moves to the brief", async ({ page }) => {
  await page.goto("/");
  const skip = page.getByRole("link", { name: "Skip to content" });
  await skip.focus();
  await page.keyboard.press("Enter");
  await expect(page.locator("#main")).toBeFocused();
  await expect(page.getByRole("heading", { name: "Morning brief" })).toBeVisible();
});

test("decisions use Apply and Not now", async ({ page, request }) => {
  const title = `Queue ${Date.now()}`;
  const created = await request.post("/action-requests", {
    data: { title, mode: "observe", detail: "Approving only records that you saw it." },
  });
  expect(created.ok()).toBeTruthy();
  await page.goto("/");
  await page.getByRole("button", { name: "Decisions" }).click();
  await expect(page.getByRole("heading", { name: "Decisions" })).toBeVisible();
  const card = page.locator("[data-kind='approval']", { hasText: title });
  await expect(card.getByRole("button", { name: "Approve" })).toBeVisible();
  await expect(card.getByRole("button", { name: "Not now" })).toBeVisible();
});

test("shopping add and tick stays on the brief", async ({ page }) => {
  const name = `Oat milk ${Date.now()}`;
  await page.goto("/");
  await page.getByRole("navigation", { name: "House" }).getByRole("button", { name: "Brief" }).click();
  await page.getByLabel("Add a shop item").fill(name);
  await page.getByRole("button", { name: "Add", exact: true }).click();
  const line = page.getByRole("checkbox", { name });
  await expect(line).toBeVisible();
  await line.click();
  await expect(line).toBeChecked();
});

test("assistant switch persists and writes an activity line", async ({ page, request }) => {
  await page.goto("/");
  await page.getByRole("navigation", { name: "House" }).getByRole("button", { name: "Settings" }).click();
  const toggle = page.getByRole("switch", { name: "Assistant" });
  await expect(toggle).toBeVisible();
  const startedOn = await toggle.isChecked();
  await toggle.click();
  await expect(toggle).toBeChecked({ checked: !startedOn });

  await page.reload();
  await page.getByRole("navigation", { name: "House" }).getByRole("button", { name: "Settings" }).click();
  await expect(page.getByRole("switch", { name: "Assistant" })).toBeChecked({ checked: !startedOn });

  const activity = await request.get("/agent/activity?limit=20");
  expect(activity.ok()).toBeTruthy();
  const body = await activity.json();
  const texts = body.items.map((item: { text: string }) => item.text);
  expect(texts.some((text: string) => text.startsWith("Assistant switched"))).toBeTruthy();

  await page.getByRole("switch", { name: "Assistant" }).click();
  await expect(page.getByRole("switch", { name: "Assistant" })).toBeChecked({ checked: startedOn });
});

test("recent activity sits above the working steps", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Decisions" }).click();
  const activity = page.getByRole("list", { name: "Recent activity" });
  await expect(activity).toBeVisible();
  const count = await activity.locator("li").count();
  expect(count).toBeGreaterThan(0);
  expect(count).toBeLessThanOrEqual(5);
  const ticker = page.locator("[data-module=reasoning] .ticker-line").first();
  await expect(ticker).toBeVisible();
  const activityBox = await activity.boundingBox();
  const tickerBox = await ticker.boundingBox();
  expect(activityBox && tickerBox && activityBox.y < tickerBox.y).toBeTruthy();
});

test("smart add stays hidden while the assistant is off", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByLabel("Add to the log")).toHaveCount(0);
  await expect(page.getByText("The assistant is off.").first()).toBeVisible();
});

test("the brief says when the commute is not connected", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("navigation", { name: "House" }).getByRole("button", { name: "Brief" }).click();
  await expect(page.getByText("Commute is not connected.").first()).toBeVisible();
});

test("a past date keeps Apply and Not now", async ({ page, request }) => {
  const created = await request.post("/agent/proposals", {
    data: { title: "Mend the stair rod", due_on: "2020-01-01", reason: "It was due." },
  });
  expect(created.ok()).toBeTruthy();
  await page.goto("/");
  await page.getByRole("button", { name: "Decisions" }).click();
  const card = page.locator(".proposal-card", { hasText: "This date has passed." });
  await expect(card).toBeVisible();
  await expect(card.getByRole("button", { name: "Apply" })).toBeVisible();
  await expect(card.getByRole("button", { name: "Not now" })).toBeVisible();
  await card.getByRole("button", { name: "Not now" }).click();
  await expect(card).toHaveCount(0);
});
