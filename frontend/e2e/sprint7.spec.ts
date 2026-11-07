import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

test("X connect, cards, a confirmed post, expiry, and the playlist line", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  let connected = false;

  await page.route("**/x/status", async (route) => {
    await route.fulfill({
      json: connected
        ? {
            enabled: true,
            configured: true,
            connected: true,
            username: "nickhome",
            watches: [{ id: "watch-1", kind: "keyword", value: "bins" }],
          }
        : { enabled: true, configured: true, connected: false, username: null, watches: [] },
    });
  });
  await page.route("**/x/connect", async (route) => {
    connected = true;
    await route.fulfill({ json: { authorize_url: "/?x=connected" } });
  });
  await page.route("**/x/poll", async (route) => {
    await route.fulfill({ json: { ran: false, reason: "cached" } });
  });
  await page.route("**/x/items", async (route) => {
    if (route.request().method() !== "GET") {
      await route.fallback();
      return;
    }
    await route.fulfill({
      json: {
        enabled: true,
        items: [
          {
            id: "b1",
            kind: "bookmark",
            summary: "Put the bins out tonight",
            detail: "@housebin",
            url: null,
            expires_at: null,
          },
          {
            id: "w1",
            kind: "watch_match",
            summary: "Council collection moved to Friday",
            detail: "@housebin",
            url: null,
            expires_at: null,
          },
          {
            id: "d1",
            kind: "draft",
            summary: "The boiler filter is in the hall",
            detail: "Say it once.",
            url: null,
            expires_at: "2099-01-01T00:00:00Z",
          },
          {
            id: "d0",
            kind: "draft",
            summary: "This draft expired",
            detail: "Old.",
            url: null,
            expires_at: "2000-01-01T00:00:00Z",
          },
        ],
      },
    });
  });
  await page.route("**/x/items/b1/apply", async (route) => {
    await route.fulfill({ json: { id: "b1", status: "applied" } });
  });
  await page.route("**/x/items/d1/post", async (route) => {
    expect(route.request().postDataJSON()).toEqual({ confirm: true });
    await route.fulfill({ json: { id: "d1", status: "posted", tweet_id: "9001" } });
  });
  await page.route("**/playlist", async (route) => {
    await route.fulfill({
      json: {
        shown: true,
        offline: false,
        title: "Morning Haze",
        genre: "Dub",
        artwork_url: "https://img.hearthis.at/art/thumb.jpg",
        permalink_url: "https://hearthis.at/chlorophil/morning-haze/",
      },
    });
  });

  await page.goto("/");
  const panel = page.locator("[data-panel='x']");
  await expect(panel.getByRole("heading", { name: "X" })).toBeVisible();
  const connect = panel.getByRole("button", { name: "Connect" });
  await expect(connect).toBeVisible();
  const connectBox = await connect.boundingBox();
  expect(connectBox?.height).toBeGreaterThanOrEqual(44);
  expect(connectBox?.width).toBeGreaterThanOrEqual(44);
  const duration = await connect.evaluate((node) => getComputedStyle(node).transitionDuration);
  expect(duration === "0s" || duration.startsWith("0s")).toBe(true);
  await connect.click();
  const connectDialog = page.getByRole("dialog");
  await expect(connectDialog.getByRole("heading", { name: "Open X to connect?" })).toBeVisible();
  await expect(connectDialog.getByText("Nothing is posted.")).toBeVisible();
  await connectDialog.getByRole("button", { name: "Connect" }).click();
  await page.waitForURL("**/?x=connected");

  await expect(page.getByText("Put the bins out tonight")).toBeVisible();
  await expect(page.getByText("Council collection moved to Friday")).toBeVisible();
  await expect(page.getByText("This draft expired")).toHaveCount(0);

  const apply = page.getByRole("button", { name: "Apply Put the bins out tonight" });
  const applyBox = await apply.boundingBox();
  expect(applyBox?.height).toBeGreaterThanOrEqual(44);
  await apply.click();
  await expect(page.getByText("Kept. Nothing was sent.")).toBeVisible();

  await page.getByRole("button", { name: "Post The boiler filter is in the hall" }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog.getByRole("heading", { name: "Post this to X?" })).toBeVisible();
  await expect(dialog.getByText("Nothing is posted until you confirm.")).toBeVisible();
  await dialog.getByRole("button", { name: "Post" }).click();
  await expect(page.getByText("Posted.")).toBeVisible();

  const playlist = page.getByRole("link", { name: /Morning Haze/ });
  await expect(playlist).toBeVisible();
  await expect(playlist).toHaveAttribute("href", "https://hearthis.at/chlorophil/morning-haze/");
  await expect(playlist).toHaveAttribute("target", "_blank");
  const linkBox = await playlist.boundingBox();
  expect(linkBox?.height).toBeGreaterThanOrEqual(44);
  await expect(page.locator("audio, video")).toHaveCount(0);

  const home = await new AxeBuilder({ page }).analyze();
  expect(home.violations).toEqual([]);

  await expect(page.getByText("Connected as @nickhome")).toBeVisible();
  const decisions = page.locator("[data-panel='reasoning']");
  await expect(decisions.getByRole("heading", { name: "Decisions" })).toBeVisible();
  await expect(decisions.getByRole("list", { name: "Recent activity" })).toBeVisible();
  await expect(page.locator("[data-panel='today']").getByRole("heading", { name: "Proposed changes" })).toBeVisible();

  await page.getByRole("button", { name: "Settings" }).click();
  await expect(page.getByText("X is on the home screen, in its own card.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Connect" })).toHaveCount(0);
  const settings = await new AxeBuilder({ page }).analyze();
  expect(settings.violations).toEqual([]);
});
