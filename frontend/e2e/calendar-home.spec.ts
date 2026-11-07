import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

const OUTSIDE = /googleapis|mistral\.ai|tfl\.gov|open-meteo|postcodes\.io/i;

const today = {
  key: "appointments",
  title: "Appointments",
  placeholder: false,
  summary: "1 appointment",
  footnote: "Read only. This is not a calendar.",
  items: [{ title: "Test data: put the bins out", meta: "09:30", ref: "fixturebins" }],
};

const emptyDay = {
  key: "appointments",
  title: "Appointments",
  placeholder: false,
  summary: "Nothing on the diary today.",
  footnote: "Read only. This is not a calendar.",
  items: [],
};

const commute = {
  summary: "Commute is not connected.",
  shift: null,
  home: { state: "missing", check: "not_verified", label: "Home" },
  destination: { state: "missing", check: "not_verified", label: "Destination" },
  arrival_buffer_minutes: 0,
  return_buffer_minutes: 0,
  outward: null,
  back: null,
  advisory: { active: false, state: "inactive", detail: "Pre-departure disruption checks are not active." },
};

const lines = {
  configured: false,
  state: "missing",
  stale: false,
  fetched_at: null,
  source_at: null,
  failure: null,
  detail: "TfL is not configured.",
  lines: [],
};

function brief(appointments: unknown) {
  return {
    title: "Morning brief",
    as_of: "2026-11-07T18:00:00+00:00",
    house_date: "2026-11-07",
    paused: false,
    note: null,
    sections: [
      { key: "tasks", title: "Tasks", placeholder: false, summary: "Nothing needs doing.", items: [] },
      { key: "commitments", title: "Open commitments", placeholder: false, summary: "None open.", items: [] },
      appointments,
    ],
  };
}

async function install(page: Page, appointments: unknown, status = 200) {
  await page.route(OUTSIDE, (route) => route.abort());
  await page.route("**/*", async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname;
    if (path === "/brief/morning") {
      if (status !== 200) {
        await route.fulfill({
          status,
          contentType: "application/json",
          body: JSON.stringify({ detail: "The brief did not answer." }),
        });
        return;
      }
      await route.fulfill({ json: brief(appointments) });
      return;
    }
    const quiet: Record<string, unknown> = {
      "/system": {
        paused: false,
        activity: "home",
        status_text: "Nothing is waiting.",
        house_date: "2026-11-07",
        updated_at: "2026-11-07T18:00:00+00:00",
        greeting: "Good evening",
        greeting_reason: "clock",
        arrived_at: null,
        debounce_until: null,
      },
      "/tasks": { items: [] },
      "/agent": { enabled: false, paused: false, reachable: true, proposals: [], due: null, last_reply: null },
      "/approvals": { items: [] },
      "/x/items": { enabled: false, items: [] },
      "/commute/plan": commute,
      "/tfl/status": lines,
      "/alerts": { items: [] },
      "/catch-up/look": { paused: false, quiet: true, items: [] },
      "/playlist": { shown: false, offline: false, title: null, genre: null, artwork_url: null, permalink_url: null },
    };
    if (path in quiet) {
      await route.fulfill({ json: quiet[path] });
      return;
    }
    await route.fallback();
  });
}

test("calendar home shows today's fixture beside commute and lines", async ({ page }) => {
  await install(page, today);
  await page.setViewportSize({ width: 1280, height: 900 });
  await page.goto("/");
  const board = page.locator("[data-home-board]");
  const calendar = board.getByRole("button", { name: /Calendar/ });
  const commuteRow = board.getByRole("button", { name: /Commute/ });
  const linesRow = board.getByRole("button", { name: /Lines/ });
  await expect(calendar).toContainText("1 appointment");
  await expect(calendar).toContainText("Test data: put the bins out");
  await expect(commuteRow).toContainText("Commute is not connected.");
  await expect(linesRow).toContainText("TfL is not configured.");

  await calendar.click();
  await expect(page.getByRole("heading", { name: "Calendar" })).toBeVisible();
  await expect(page.getByText("Today only. Read only. This is not a calendar.")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Test data: put the bins out" })).toBeVisible();
  await expect(page.getByText("09:30")).toBeVisible();
  const desktopDetail = await page.locator("#home-detail").boundingBox();
  const desktopBoard = await board.boundingBox();
  expect(desktopDetail && desktopBoard && desktopDetail.x > desktopBoard.x).toBeTruthy();
  await board.screenshot({ path: "/opt/cursor/artifacts/screenshot_calendar_home_desktop.png" });

  const brief = board.getByRole("button", { name: /Brief/ });
  await brief.click();
  await brief.focus();
  await page.keyboard.press("ArrowDown");
  await expect(calendar).toHaveAttribute("aria-expanded", "true");
  await page.keyboard.press("ArrowDown");
  await expect(page.getByRole("heading", { name: "Commute" })).toBeVisible();
  await expect(commuteRow).toHaveAttribute("aria-expanded", "true");
  await page.keyboard.press("ArrowDown");
  await expect(page.getByRole("heading", { name: "Line status" })).toBeVisible();
  await expect(linesRow).toHaveAttribute("aria-expanded", "true");

  await page.setViewportSize({ width: 390, height: 844 });
  await calendar.click();
  await expect(page.getByRole("heading", { name: "Test data: put the bins out" })).toBeVisible();
  const mobileDetail = await page.locator("#home-detail").boundingBox();
  const mobileBoard = await board.boundingBox();
  expect(mobileDetail && mobileBoard && mobileDetail.width).toBeGreaterThan((mobileBoard?.width ?? 0) * 0.9);
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow).toBeLessThanOrEqual(1);
  await board.screenshot({ path: "/opt/cursor/artifacts/screenshot_calendar_home_mobile.png" });

  const results = await new AxeBuilder({ page }).analyze();
  expect(results.violations).toEqual([]);
});

test("an empty diary day stays on the calendar row", async ({ page }) => {
  await install(page, emptyDay);
  await page.goto("/");
  const calendar = page.locator("[data-home-board]").getByRole("button", { name: /Calendar/ });
  await expect(calendar).toContainText("Nothing on the diary today.");
  await calendar.click();
  await expect(page.getByText("Today only. Read only. This is not a calendar.")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Test data: put the bins out" })).toHaveCount(0);
});

test("a failed brief is shown on the calendar row", async ({ page }) => {
  await install(page, emptyDay, 503);
  await page.goto("/");
  const calendar = page.locator("[data-home-board]").getByRole("button", { name: /Calendar/ });
  await expect(calendar).toContainText("The diary could not be read.");
  await expect(calendar).toContainText("The brief did not answer.");
  await calendar.click();
  await expect(page.getByRole("alert")).toContainText("The brief did not answer.");
  await expect(page.getByText(/last check/i)).toHaveCount(0);
});
