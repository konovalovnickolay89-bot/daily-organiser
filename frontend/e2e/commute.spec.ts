import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

const OUTSIDE = /googleapis|mistral\.ai|tfl\.gov|open-meteo|postcodes\.io/i;

const places = {
  home: { state: "configured", check: "not_verified", kind: "coordinates", label: "Home" },
  destination: {
    state: "configured",
    check: "not_verified",
    label: "Wembley Park",
    override: "default",
    note: null,
  },
};

const inactive = {
  active: false,
  state: "inactive",
  detail: "Pre-departure disruption checks are not active.",
};

function leg(
  role: "outward" | "return",
  timeIs: "Arriving" | "Departing",
  target: string,
  clock: string | null,
  meta: string,
  minutes: number | null,
) {
  return {
    role,
    time_is: timeIs,
    target,
    clock,
    minutes,
    lines: minutes == null ? [] : ["Jubilee"],
    detail: minutes == null ? "Journey check is not connected." : `${minutes} min · Jubilee. No line disruptions.`,
    meta,
    state: minutes == null ? "unconnected" : "planned",
  };
}

const today = {
  summary: "Wembley Park · leave 07:22 · 34 min · Jubilee. No line disruptions. Back departs 16:05.",
  shift: {
    id: "today",
    start: "2026-11-07T08:00:00+00:00",
    end: "2026-11-07T16:00:00+00:00",
    location_label: "Wembley",
    when: "today",
    overnight: false,
  },
  ...places,
  arrival_buffer_minutes: 10,
  return_buffer_minutes: 0,
  outward: leg("outward", "Arriving", "2026-11-07T07:50:00+00:00", "07:22", "Arrive by 07:50", 34),
  back: leg("return", "Departing", "2026-11-07T16:00:00+00:00", "16:05", "Departs at the finish 16:00", 36),
  advisory: inactive,
};

const future = {
  ...today,
  summary: "Wembley Park · Sun 8 Nov · 22:00–06:30. Journey check is not connected.",
  shift: {
    id: "future",
    start: "2026-11-08T22:00:00+00:00",
    end: "2026-11-09T06:30:00+00:00",
    location_label: "Wembley",
    when: "upcoming",
    overnight: true,
  },
  outward: leg("outward", "Arriving", "2026-11-08T21:50:00+00:00", null, "Arrive by 21:50", null),
  back: leg("return", "Departing", "2026-11-09T06:30:00+00:00", null, "Departs at the finish 06:30", null),
};

const overnight = {
  ...today,
  summary: "Wembley Park · 22:00–06:00. Journey check is not connected.",
  shift: {
    id: "overnight",
    start: "2026-03-28T22:00:00+00:00",
    end: "2026-03-29T05:00:00+00:00",
    location_label: "Wembley",
    when: "overnight",
    overnight: true,
  },
  outward: leg("outward", "Arriving", "2026-03-28T21:50:00+00:00", "21:40", "Arrive by 21:50", 28),
  back: leg("return", "Departing", "2026-03-29T05:15:00+00:00", "06:15", "Departs 15 min after the finish", 31),
};

const zero = {
  summary: "No commute on the rota today.",
  shift: null,
  ...places,
  home: { state: "missing", check: "not_verified", kind: null, label: "Home" },
  arrival_buffer_minutes: 10,
  return_buffer_minutes: 0,
  outward: null,
  back: null,
  advisory: inactive,
};

const stale = {
  ...today,
  advisory: {
    active: true,
    state: "stale",
    detail: "Showing the last disruption check. A newer read failed. Jubilee: Minor Delays",
  },
};

const broken = {
  ...zero,
  summary: "Journey check is unavailable.",
  advisory: { active: true, state: "error", detail: "Disruption check is unavailable." },
};

function board(page: Page) {
  return page.locator("[data-home-board]");
}

async function show(page: Page, plan: object) {
  await page.route(OUTSIDE, (route) => route.abort());
  await page.route("**/commute/plan", async (route) => {
    expect(route.request().method()).toBe("GET");
    await route.fulfill({ json: plan });
  });
  await page.setViewportSize({ width: 1280, height: 900 });
  await page.goto("/");
  const row = board(page).getByRole("button", { name: /Commute/ });
  await row.click();
  return row;
}

test("a day with no shift stays on the overview and says the check is not active", async ({ page }) => {
  await page.route(OUTSIDE, (route) => route.abort());
  await page.goto("/");
  const row = board(page).getByRole("button", { name: /Commute/ });
  await expect(row).toContainText(/Commute is not connected|No commute on the rota today/);
  await row.click();
  await expect(page.getByText("Pre-departure disruption checks are not active.")).toBeVisible();
  await expect(page.locator("[data-places]")).toContainText("Not verified with a provider.");
  await expect(page.locator("[data-places]")).not.toContainText(/\bVerified\b/);
  await expect(page.getByRole("heading", { name: "Line status" })).toHaveCount(0);
});

test("today, a later shift, overnight, stale, and error stay in the commute pane", async ({ page }) => {
  const row = await show(page, today);
  await expect(row).toContainText("Today · Out 07:22 · back 16:05");
  await expect(row).toContainText("34");
  await expect(page.locator("[data-leg='outward']")).toContainText("Arrive by 07:50");
  await expect(page.locator("[data-leg='return']")).toContainText("Departs at the finish 16:00");
  await expect(page.locator("[data-advisory='inactive']")).toContainText("not active");
  await expect(page.locator("[data-places]")).toContainText("Home is configured. Not verified with a provider.");
  await expect(page.locator("[data-places]")).toContainText("Wembley Park is configured. Not verified with a provider.");

  await page.unroute("**/commute/plan");
  await page.route("**/commute/plan", async (route) => route.fulfill({ json: future }));
  await page.reload();
  await board(page).getByRole("button", { name: /Commute/ }).click();
  await expect(board(page).getByRole("button", { name: /Commute/ })).toContainText("Next shift");
  await expect(page.getByText("Arrive by 21:50")).toBeVisible();
  await expect(page.getByText("Departs at the finish 06:30")).toBeVisible();

  await page.unroute("**/commute/plan");
  await page.route("**/commute/plan", async (route) => route.fulfill({ json: overnight }));
  await page.reload();
  await board(page).getByRole("button", { name: /Commute/ }).click();
  await expect(board(page).getByRole("button", { name: /Commute/ })).toContainText("Overnight");
  await expect(page.locator("[data-leg='outward']")).toContainText("21:50");
  await expect(page.locator("[data-leg='return']")).toContainText("06:15");

  await page.unroute("**/commute/plan");
  await page.route("**/commute/plan", async (route) => route.fulfill({ json: stale }));
  await page.reload();
  const staleRow = board(page).getByRole("button", { name: /Commute/ });
  await expect(staleRow).toContainText("newer read failed");
  await staleRow.click();
  const advisory = page.locator("[data-advisory='stale']");
  await expect(advisory).toContainText("Jubilee: Minor Delays");
  expect((await advisory.innerText()).toLowerCase()).not.toMatch(/real-?time|\blive\b/);

  await page.unroute("**/commute/plan");
  await page.route("**/commute/plan", async (route) => route.fulfill({ json: broken }));
  await page.reload();
  await board(page).getByRole("button", { name: /Commute/ }).click();
  await expect(page.locator("[data-advisory='error']")).toContainText("Disruption check is unavailable.");

  await page.unroute("**/commute/plan");
  await page.route("**/commute/plan", async (route) => route.fulfill({ json: zero }));
  await page.reload();
  await expect(board(page).getByRole("button", { name: /Commute/ })).toContainText("No commute on the rota today.");
});

test("the commute pane sits beside the overview and under it on a phone", async ({ page }) => {
  await show(page, today);
  const rail = page.getByRole("navigation", { name: "House" });
  await rail.getByRole("button", { name: "Settings" }).click();
  await page.getByRole("radio", { name: "Morning" }).check();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "morning");
  await rail.getByRole("button", { name: "Home" }).click();
  await board(page).getByRole("button", { name: /Commute/ }).click();
  const desktopDetail = await page.locator("#home-detail").boundingBox();
  const desktopBoard = await board(page).boundingBox();
  expect(desktopDetail && desktopBoard && desktopDetail.x > desktopBoard.x).toBeTruthy();
  await board(page).screenshot({ path: test.info().outputPath("commute-desktop.png") });

  await rail.getByRole("button", { name: "Settings" }).click();
  await page.getByRole("radio", { name: "Evening" }).check();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "evening");
  await page.setViewportSize({ width: 390, height: 844 });
  await rail.getByRole("button", { name: "Home" }).click();
  await board(page).getByRole("button", { name: /Commute/ }).click();
  const mobileDetail = await page.locator("#home-detail").boundingBox();
  const mobileBoard = await board(page).boundingBox();
  expect(mobileDetail && mobileBoard && mobileDetail.width).toBeGreaterThan((mobileBoard?.width ?? 0) * 0.9);
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow).toBeLessThanOrEqual(1);
  await board(page).screenshot({ path: test.info().outputPath("commute-mobile.png") });

  const results = await new AxeBuilder({ page }).analyze();
  expect(results.violations).toEqual([]);
});

const lineStatus = {
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
    { id: "central", name: "Central", mode: "Tube", severity: "Good Service", reason: null },
  ],
};

test("lines and the round trip share Home while departure checks stay off", async ({ page }) => {
  let outside = 0;
  await page.route(OUTSIDE, (route) => {
    outside += 1;
    return route.abort();
  });
  await page.route("**/commute/plan", async (route) => {
    expect(route.request().method()).toBe("GET");
    await route.fulfill({ json: today });
  });
  await page.route("**/tfl/status", async (route) => {
    expect(route.request().method()).toBe("GET");
    expect(new URL(route.request().url()).search).toBe("");
    await route.fulfill({ json: lineStatus });
  });
  await page.setViewportSize({ width: 1280, height: 900 });
  await page.goto("/");
  const home = board(page);
  const commute = home.getByRole("button", { name: /Commute/ });
  const lines = home.getByRole("button", { name: /Lines/ });
  await expect(commute).toContainText("Today · Out 07:22 · back 16:05");
  await expect(lines).toContainText("1 line disrupted.");
  await expect(lines).toContainText("Jubilee: Minor Delays");

  const brief = home.getByRole("button", { name: /Brief/ });
  await brief.focus();
  await page.keyboard.press("ArrowDown");
  await expect(page.getByRole("heading", { name: "Calendar" })).toBeVisible();
  await page.keyboard.press("ArrowDown");
  await expect(page.getByRole("heading", { name: "Commute" })).toBeVisible();
  await expect(page.locator("[data-advisory='inactive']")).toContainText("not active");
  await expect(commute).toHaveAttribute("aria-expanded", "true");
  await page.keyboard.press("ArrowDown");
  await expect(page.getByRole("heading", { name: "Line status" })).toBeVisible();
  await expect(page.getByText("Minor delays due to a signal failure at Baker Street.")).toBeVisible();
  await expect(lines).toHaveAttribute("aria-expanded", "true");
  await expect(commute).toContainText("Today · Out 07:22 · back 16:05");
  await page.keyboard.press("ArrowDown");
  await expect(page.getByRole("heading", { name: "Today" })).toBeVisible();

  const rail = page.getByRole("navigation", { name: "House" });
  await rail.getByRole("button", { name: "Settings" }).click();
  await expect(page.getByRole("heading", { name: "Line status" })).toHaveCount(0);
  await expect(page.getByText("The journey source is not connected.")).toHaveCount(0);
  await expect(page.locator(".fact-row", { hasText: "Disruption checks" }).locator("dd")).toHaveText("Not active");
  expect(outside).toBe(0);

  await page.getByRole("radio", { name: "Morning" }).check();
  await rail.getByRole("button", { name: "Home" }).click();
  await lines.click();
  await home.screenshot({ path: test.info().outputPath("home-lines-desktop.png") });
  await commute.click();
  await home.screenshot({ path: test.info().outputPath("home-commute-desktop.png") });

  await rail.getByRole("button", { name: "Settings" }).click();
  await page.getByRole("radio", { name: "Evening" }).check();
  await page.setViewportSize({ width: 390, height: 844 });
  await rail.getByRole("button", { name: "Home" }).click();
  await commute.click();
  const mobileDetail = await page.locator("#home-detail").boundingBox();
  const mobileBoard = await home.boundingBox();
  expect(mobileDetail && mobileBoard && mobileDetail.width).toBeGreaterThan((mobileBoard?.width ?? 0) * 0.9);
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow).toBeLessThanOrEqual(1);
  await home.screenshot({ path: test.info().outputPath("home-both-mobile.png") });
  await lines.click();
  await expect(page.getByRole("heading", { name: "Jubilee" })).toBeVisible();
});
