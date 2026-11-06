import { expect, test } from "@playwright/test";

test("skip link moves to the brief", async ({ page }) => {
  await page.goto("/");
  const skip = page.getByRole("link", { name: "Skip to content" });
  await skip.focus();
  await page.keyboard.press("Enter");
  await expect(page.locator("#main")).toBeFocused();
  await expect(page.getByRole("heading", { name: "Morning brief" })).toBeVisible();
});

test("decisions use Apply and Not now", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Decisions" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Apply" }).first()).toBeVisible();
  await expect(page.getByRole("button", { name: "Not now" }).first()).toBeVisible();
});

test("shopping add and tick stays on the brief", async ({ page }) => {
  const name = `Oat milk ${Date.now()}`;
  await page.goto("/");
  await page.getByRole("button", { name: "Brief" }).click();
  await page.getByLabel("Add a shop item").fill(name);
  await page.getByRole("button", { name: "Add", exact: true }).click();
  const line = page.getByRole("checkbox", { name });
  await expect(line).toBeVisible();
  await line.click();
  await expect(line).toBeChecked();
});

test("assistant switch persists and writes an activity line", async ({ page, request }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Settings" }).click();
  const toggle = page.getByRole("switch", { name: "Assistant" });
  await expect(toggle).toBeVisible();
  const startedOn = await toggle.isChecked();
  await toggle.click();
  await expect(toggle).toBeChecked({ checked: !startedOn });

  await page.reload();
  await page.getByRole("button", { name: "Settings" }).click();
  await expect(page.getByRole("switch", { name: "Assistant" })).toBeChecked({ checked: !startedOn });

  const activity = await request.get("/agent/activity?limit=20");
  expect(activity.ok()).toBeTruthy();
  const body = await activity.json();
  const texts = body.items.map((item: { text: string }) => item.text);
  expect(texts.some((text: string) => text.startsWith("Assistant switched"))).toBeTruthy();

  await page.getByRole("switch", { name: "Assistant" }).click();
  await expect(page.getByRole("switch", { name: "Assistant" })).toBeChecked({ checked: startedOn });
});
