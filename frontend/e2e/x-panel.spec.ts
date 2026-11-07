import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

const connected = {
  enabled: true,
  configured: true,
  connected: true,
  username: "nickhome",
  watches: [{ id: "watch-1", kind: "keyword", value: "bins" }],
  poll_paused: false,
  poll_interval_minutes: 30,
  last_poll_at: "2026-11-06T08:05:00+00:00",
  last_error_class: null,
  backing_off: false,
  backoff_until: null,
  credits_remaining: 120,
  rate_remaining: 45,
  rate_reset_at: "2026-11-06T09:00:00+00:00",
  watch_limit: 20,
};

async function mockX(page: Page, status: Record<string, unknown>) {
  let current = status;
  await page.route("**/x/status", async (route) => {
    await route.fulfill({ json: current });
  });
  await page.route("**/x/items", async (route) => {
    await route.fulfill({ json: { enabled: true, items: [] } });
  });
  await page.route("**/x/poll", async (route) => {
    await route.fulfill({ json: { ran: false, reason: current.poll_paused ? "poll_paused" : "cached" } });
  });
  await page.route("**/x/poll/pause", async (route) => {
    current = { ...current, poll_paused: true };
    await route.fulfill({ json: current });
  });
  await page.route("**/x/poll/resume", async (route) => {
    current = { ...current, poll_paused: false };
    await route.fulfill({ json: current });
  });
  await page.route("**/x/watches", async (route) => {
    if (route.request().method() === "POST") {
      await route.fulfill({ status: 422, json: { detail: "Not for the house log." } });
      return;
    }
    await route.fallback();
  });
}

test("the X card sits to the right and keeps the other boxes", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 960 });
  await mockX(page, connected);
  await page.goto("/");
  const x = page.locator("[data-panel='x']");
  const decisions = page.locator("[data-panel='reasoning']");
  const today = page.locator("[data-panel='today']");
  await expect(x.getByRole("heading", { name: "X" })).toBeVisible();
  await expect(x.getByText("Connected as")).toBeVisible();
  await expect(decisions.getByRole("heading", { name: "Decisions" })).toBeVisible();
  await expect(decisions.getByRole("list", { name: "Recent activity" })).toBeVisible();
  await expect(today.getByRole("heading", { name: "Proposed changes" })).toBeVisible();
  await expect(today.getByText("The assistant is off.")).toBeVisible();

  const xBox = await x.boundingBox();
  const decisionsBox = await decisions.boundingBox();
  expect(xBox && decisionsBox && xBox.x >= decisionsBox.x + decisionsBox.width - 1).toBe(true);
  expect(await x.locator("[aria-label='Recent activity']").count()).toBe(0);

  const keyword = x.getByRole("textbox", { name: "Watch", exact: true });
  await keyword.fill("bins!");
  await expect(x.getByText("A keyword is plain words, up to 80 characters.")).toBeVisible();
  await expect(x.getByRole("button", { name: "Add" })).toBeDisabled();

  await x.getByRole("button", { name: "Pause reading" }).click();
  await expect(x.getByRole("button", { name: "Resume reading" })).toBeVisible();
  await expect(x.getByText("Reading is paused.")).toBeVisible();

  await x.getByRole("button", { name: "Disconnect" }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog.getByRole("heading", { name: "Disconnect X?" })).toBeVisible();
  await dialog.getByRole("button", { name: "Cancel" }).click();
  await expect(x.getByText("Connected as")).toBeVisible();

  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow).toBeLessThanOrEqual(1);
  const desktop = await new AxeBuilder({ page }).analyze();
  expect(desktop.violations).toEqual([]);
});

test("the X card stacks under the decisions on a narrow screen", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await mockX(page, {
    enabled: true,
    configured: false,
    connected: false,
    username: null,
    watches: [],
    poll_paused: false,
    poll_interval_minutes: 30,
    watch_limit: 20,
  });
  await page.goto("/");
  const x = page.locator("[data-panel='x']");
  const decisions = page.locator("[data-panel='reasoning']");
  await expect(x.getByText(/does not take a key/)).toBeVisible();
  await expect(x.getByRole("button", { name: "Connect" })).toBeDisabled();
  const xBox = await x.boundingBox();
  const decisionsBox = await decisions.boundingBox();
  expect(xBox && decisionsBox && xBox.y >= decisionsBox.y + 40).toBe(true);
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow).toBeLessThanOrEqual(1);
  const mobile = await new AxeBuilder({ page }).analyze();
  expect(mobile.violations).toEqual([]);
});

test("an off house shows X as off", async ({ page }) => {
  await page.goto("/");
  const x = page.locator("[data-panel='x']");
  await expect(x.getByText(/The house file has to turn it on/)).toBeVisible();
  await expect(x.getByRole("button", { name: "Connect" })).toBeDisabled();
  await expect(x.getByRole("button", { name: "Pause reading" })).toBeDisabled();
});
