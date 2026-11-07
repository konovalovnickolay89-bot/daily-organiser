import { expect, test, type Page, type Route } from "@playwright/test";

const OUTSIDE = /googleapis|mistral\.ai|tfl\.gov|open-meteo|postcodes\.io/i;

test.beforeEach(async ({ page }) => {
  await page.route(OUTSIDE, (route) => route.abort());
});

test("the playlist line stays hidden", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText("A playlist is ready, when you want it.")).toHaveCount(0);
});

test("pause and unpause stay on the house", async ({ page }) => {
  await page.goto("/");
  const pause = page.getByRole("button", { name: "Pause the house" });
  await pause.click();
  await expect(page.getByRole("button", { name: "Unpause the house" })).toBeVisible();
  await expect(page.getByText("Paused", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Unpause the house" }).click();
  await expect(page.getByRole("button", { name: "Pause the house" })).toBeVisible();
  await expect(page.getByText("All quiet")).toBeVisible();
});

test("brief sections say when diary and weather are not set", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("navigation", { name: "House" }).getByRole("button", { name: "Brief" }).click();
  await expect(page.getByText("Diary not connected — reconnect in Settings.").first()).toBeVisible();
  await expect(page.getByText("Weather location is not set.").first()).toBeVisible();
});

test("settings show the commute is not connected and can hold a theme", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("navigation", { name: "House" }).getByRole("button", { name: "Settings" }).click();
  await expect(page.locator(".fact-row", { hasText: "TfL" }).locator("dd")).toHaveText("Not configured");
  await expect(page.getByText("TfL is not configured.")).toBeVisible();
  await expect(page.getByText("The journey source is not connected.")).toHaveCount(0);

  await page.getByRole("radio", { name: "Morning" }).check();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "morning");
  await page.getByRole("radio", { name: "Evening" }).check();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "evening");
  await page.getByRole("radio", { name: "House clock" }).check();
});

test("an approval in Decisions can be applied", async ({ page, request }) => {
  const created = await request.post("/action-requests", {
    data: { title: `See the note ${Date.now()}`, mode: "observe", detail: "Approving only records that you saw it." },
  });
  expect(created.ok()).toBeTruthy();
  const title = (await created.json()).title as string;
  await page.goto("/");
  await page.getByRole("button", { name: "Decisions" }).click();
  const card = page.locator("[data-kind='approval']", { hasText: title });
  await expect(card).toBeVisible();
  await card.getByRole("button", { name: "Apply" }).click();
  await expect(card).toHaveCount(0);
});

test("Not now dismisses an approval", async ({ page, request }) => {
  const created = await request.post("/action-requests", {
    data: { title: `Later ${Date.now()}`, mode: "advise", detail: "Nothing will be booked." },
  });
  const title = (await created.json()).title as string;
  await page.goto("/");
  await page.getByRole("button", { name: "Decisions" }).click();
  const card = page.locator("[data-kind='approval']", { hasText: title });
  await card.getByRole("button", { name: "Not now" }).click();
  await expect(card).toHaveCount(0);
});

test("marking a task done can be undone", async ({ page, request }) => {
  const title = `Water ${Date.now()}`;
  const today = (await (await request.get("/system")).json()).house_date as string;
  const created = await request.post("/tasks", { data: { title, due_on: today } });
  expect(created.ok()).toBeTruthy();
  await page.goto("/");
  await page.getByRole("navigation", { name: "House" }).getByRole("button", { name: "Tasks" }).click();
  await page.getByRole("button", { name: new RegExp(`Open ${title}`) }).click();
  await page.getByRole("button", { name: "Mark done" }).click();
  await expect(page.getByText("Marked done.")).toBeVisible();
  await page.getByRole("button", { name: "Undo" }).click();
  await expect(page.getByRole("button", { name: new RegExp(`Open ${title}`) })).toBeVisible();
});

test("deleting a task can be undone", async ({ page, request }) => {
  const title = `Bulb ${Date.now()}`;
  const today = (await (await request.get("/system")).json()).house_date as string;
  expect((await request.post("/tasks", { data: { title, due_on: today } })).ok()).toBeTruthy();
  await page.goto("/");
  await page.getByRole("navigation", { name: "House" }).getByRole("button", { name: "Tasks" }).click();
  await page.getByRole("button", { name: new RegExp(`Open ${title}`) }).click();
  await page.getByRole("button", { name: "Delete" }).click();
  await page.getByRole("button", { name: "Delete" }).click();
  await expect(page.getByText("Task deleted.")).toBeVisible();
  await expect(page.getByRole("button", { name: new RegExp(`Open ${title}`) })).toHaveCount(0);
  await page.getByRole("button", { name: "Undo" }).click();
  await expect(page.getByRole("button", { name: new RegExp(`Open ${title}`) })).toBeVisible();
});

test("smart add proposes and Apply uses a fake assistant", async ({ page }) => {
  const card = proposal("Buy oat milk");
  await installAssistant(page, card);
  await page.goto("/");
  await page.getByRole("button", { name: "Proposed changes" }).click();
  await page.getByLabel("Add to the log").fill("Buy oat milk");
  await page.locator("[data-module='assistant']").getByRole("button", { name: "Add", exact: true }).click();
  await page.getByRole("button", { name: "Decisions" }).click();
  await expect(page.getByRole("heading", { name: "New task: Buy oat milk" })).toBeVisible();
  await expect(page.locator("[data-kind='proposal']").getByText("Journey source is not connected.")).toBeVisible();
  await page.locator("[data-kind='proposal']").getByRole("button", { name: "Apply" }).click();
  await expect(page.getByText("Applied: New task: Buy oat milk")).toBeVisible();
  await expect(page.getByRole("heading", { name: "New task: Buy oat milk" })).toHaveCount(0);
});

test("Not now dismisses a proposal", async ({ page }) => {
  const card = proposal("Note the filter size");
  await installAssistant(page, card);
  await page.goto("/");
  await page.getByRole("button", { name: "Proposed changes" }).click();
  await page.getByLabel("Add to the log").fill("Note the filter size");
  await page.locator("[data-module='assistant']").getByRole("button", { name: "Add", exact: true }).click();
  await page.getByRole("button", { name: "Decisions" }).click();
  await expect(page.getByRole("heading", { name: "New task: Note the filter size" })).toBeVisible();
  await page.locator("[data-kind='proposal']").getByRole("button", { name: "Not now" }).click();
  await expect(page.getByText("Dismissed. Nothing changed.")).toBeVisible();
  await expect(page.getByRole("heading", { name: "New task: Note the filter size" })).toHaveCount(0);
});

test("targets stay 44px and the page does not overflow at a 200% viewport", async ({ page }) => {
  await page.setViewportSize({ width: 640, height: 800 });
  await page.goto("/");
  const pause = page.getByRole("button", { name: "Pause the house" });
  const box = await pause.boundingBox();
  expect(box?.width).toBeGreaterThanOrEqual(44);
  expect(box?.height).toBeGreaterThanOrEqual(44);
  const rail = page.getByRole("navigation", { name: "House" }).getByRole("button", { name: "Home" });
  const railBox = await rail.boundingBox();
  expect(railBox?.width).toBeGreaterThanOrEqual(44);
  expect(railBox?.height).toBeGreaterThanOrEqual(44);
  expect(await rail.getAttribute("title")).toBe("Home");
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow).toBeLessThanOrEqual(1);
});

function proposal(title: string) {
  return {
    id: "11111111-1111-1111-1111-111111111111",
    origin: "feed",
    label: "Noted",
    summary: `New task: ${title}`,
    reason: "Journey source is not connected.",
  };
}

async function installAssistant(page: Page, card: ReturnType<typeof proposal>) {
  let proposals = [] as Array<ReturnType<typeof proposal>>;
  const state = () => ({
    enabled: true,
    paused: false,
    reachable: true,
    as_of: "2026-11-06T08:00:00+00:00",
    house_date: "2026-11-06",
    due: null,
    runs_left_today: 12,
    proactive_left_today: 3,
    last_reply: null,
    proposals,
  });

  await page.route("**/agent", async (route) => {
    if (new URL(route.request().url()).pathname !== "/agent") return route.fallback();
    await route.fulfill({ json: state() });
  });
  await page.route("**/agent/feed", async (route) => {
    proposals = [card];
    const body = [
      "event: step",
      'data: {"step":"reading"}',
      "",
      "event: step",
      'data: {"step":"calling"}',
      "",
      "event: done",
      `data: ${JSON.stringify({ reply: "Noted.", proposals })}`,
      "",
    ].join("\n");
    await route.fulfill({ status: 200, headers: { "content-type": "text/event-stream" }, body });
  });
  await page.route("**/agent/proposals/*/apply", async (route) => {
    proposals = [];
    await route.fulfill({ json: { applied: { summary: card.summary } } });
  });
  await page.route("**/agent/proposals/*/dismiss", async (route) => {
    proposals = [];
    await route.fulfill({ json: { status: "dismissed" } });
  });
  await page.route("**/agent/review", (route: Route) => route.fulfill({ status: 409, json: { detail: "Nothing is due." } }));
}
