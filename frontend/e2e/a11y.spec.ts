import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

async function expectNoViolations(page: import("@playwright/test").Page) {
  const results = await new AxeBuilder({ page }).analyze();
  expect(results.violations).toEqual([]);
}

test("home has no axe violations", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  await expectNoViolations(page);
});

test("brief has no axe violations", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Brief" }).click();
  await expect(page.getByRole("heading", { name: "Morning brief" })).toBeVisible();
  await expectNoViolations(page);
});

test("settings has no axe violations", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Settings" }).click();
  await expect(page.getByRole("heading", { name: "Settings" })).toBeVisible();
  await expectNoViolations(page);
});

test("memory screen has no axe violations", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Settings" }).click();
  await expect(page.getByRole("heading", { name: "Memory" })).toBeVisible();
  await expect(page.getByRole("searchbox", { name: "Search memory" })).toBeVisible();
  await expectNoViolations(page);
});
