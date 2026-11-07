import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

const OUTSIDE = /googleapis|mistral\.ai|tfl\.gov|open-meteo|postcodes\.io/i;

const lines = {
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
    {
      id: "london-overground",
      name: "London Overground",
      mode: "Overground",
      severity: "Good Service",
      reason: null,
    },
    {
      id: "elizabeth",
      name: "Elizabeth line",
      mode: "Elizabeth line",
      severity: "Part Suspended",
      reason: "Part suspended between Abbey Wood and Paddington while trains are held.",
    },
    {
      id: "dlr",
      name: "DLR",
      mode: "DLR",
      severity: "Good Service",
      reason: null,
    },
  ],
};

function rail(page: Page, name: string) {
  return page.getByRole("navigation", { name: "House" }).getByRole("button", { name });
}

async function install(page: Page) {
  let hits = 0;
  await page.route(OUTSIDE, (route) => route.abort());
  await page.route("**/tfl/status", async (route) => {
    hits += 1;
    const url = new URL(route.request().url());
    expect(url.search).toBe("");
    await route.fulfill({ json: lines });
  });
  await page.route("**/system/facts", async (route) => {
    const response = await route.fetch();
    const body = await response.json();
    body.tfl = "configured";
    await route.fulfill({ json: body });
  });
  return {
    hits: () => hits,
  };
}

test("line status is on Home and stays out of Settings", async ({ page }) => {
  const api = await install(page);
  await page.setViewportSize({ width: 1280, height: 900 });
  await page.goto("/");
  const board = page.locator("[data-home-board]");
  const overview = board.getByRole("button", { name: /Lines/ });
  await expect(overview).toContainText("2");
  await expect(overview).toContainText("2 lines disrupted.");
  await expect(overview).toContainText("Jubilee: Minor Delays");
  expect(api.hits()).toBe(1);

  await overview.click();
  await expect(page.getByRole("heading", { name: "Line status" })).toBeVisible();
  await expect(page.getByText("Minor delays due to a signal failure at Baker Street.")).toBeVisible();
  await expect(page.locator("[data-line='central'] [data-severity]")).toHaveText("Good Service");
  await expect(page.locator("[data-line='central'] [data-reason]")).toHaveCount(0);
  await expect(page.getByText("Part suspended between Abbey Wood and Paddington while trains are held.")).toBeVisible();
  await expect(page.getByText(/Read at/)).toBeVisible();
  await expect(page.getByText(/Source time/)).toBeVisible();
  const readout = (await page.locator("[data-readout]").innerText()).toLowerCase();
  expect(readout).not.toMatch(/real-?time|\blive\b/);
  expect(api.hits()).toBe(1);

  await board.getByRole("button", { name: /Brief/ }).click();
  await expect(page.getByText("Commute is not connected.").first()).toBeVisible();
  await expect(overview).toContainText("Jubilee: Minor Delays");
  expect(api.hits()).toBe(1);

  await rail(page, "Settings").click();
  await expect(page.locator(".fact-row", { hasText: "TfL" }).locator("dd")).toHaveText("Configured");
  await expect(page.getByRole("heading", { name: "Line status" })).toHaveCount(0);
  await expect(page.locator("[data-panel='settings']").getByText("Baker Street")).toHaveCount(0);
  await expect(page.getByText("The journey source is not connected.")).toHaveCount(0);
  expect(api.hits()).toBe(1);

  await page.getByRole("radio", { name: "Morning" }).check();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "morning");
  await rail(page, "Home").click();
  await overview.click();
  await expect(page.getByRole("heading", { name: "Jubilee" })).toBeVisible();
  expect(api.hits()).toBe(2);
  const desktopDetail = await page.locator("#home-detail").boundingBox();
  const desktopBoard = await page.locator("[data-home-board]").boundingBox();
  expect(desktopDetail && desktopBoard && desktopDetail.x > (desktopBoard.x ?? 0)).toBeTruthy();
  await page.locator("[data-home-board]").screenshot({ path: test.info().outputPath("line-status-desktop.png") });

  await rail(page, "Settings").click();
  await page.getByRole("radio", { name: "Evening" }).check();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "evening");
  await page.setViewportSize({ width: 390, height: 844 });
  await rail(page, "Home").click();
  await overview.click();
  await expect(page.getByRole("heading", { name: "Jubilee" })).toBeVisible();
  const mobileDetail = await page.locator("#home-detail").boundingBox();
  const mobileBoard = await page.locator("[data-home-board]").boundingBox();
  expect(mobileDetail && mobileBoard && mobileDetail.width).toBeGreaterThan((mobileBoard?.width ?? 0) * 0.9);
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow).toBeLessThanOrEqual(1);
  await page.locator("[data-home-board]").screenshot({ path: test.info().outputPath("line-status-mobile.png") });

  const results = await new AxeBuilder({ page }).analyze();
  expect(results.violations).toEqual([]);
});

test("a stale line status is evident on Home and is not labelled live", async ({ page }) => {
  await page.route(OUTSIDE, (route) => route.abort());
  await page.route("**/tfl/status", async (route) => {
    await route.fulfill({
      json: {
        ...lines,
        state: "stale",
        stale: true,
        failure: "timeout",
        detail: "Showing the last line status. A newer read failed. TfL did not answer in time.",
      },
    });
  });
  await page.goto("/");
  const overview = page.locator("[data-home-board]").getByRole("button", { name: /Lines/ });
  await expect(overview).toContainText("A newer read failed");
  await expect(overview).toContainText("Jubilee: Minor Delays");
  await overview.click();
  const readout = page.locator("[data-readout]");
  await expect(readout).toContainText("A newer read failed");
  await expect(readout).toContainText("TfL did not answer in time.");
  await expect(readout).toContainText("Read at");
  expect((await readout.innerText()).toLowerCase()).not.toMatch(/real-?time|\blive\b/);
  await expect(page.getByRole("heading", { name: "Jubilee" })).toBeVisible();
});
