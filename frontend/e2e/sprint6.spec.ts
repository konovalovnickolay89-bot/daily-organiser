import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

test("status panel shows health, version, and the database", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Settings" }).click();
  await expect(page.getByRole("heading", { name: "Status" })).toBeVisible();
  await expect(page.locator("[data-status='health']")).toHaveText("Ok");
  await expect(page.locator("[data-status='version']")).not.toHaveText("…");
  await expect(page.locator("[data-status='database']")).toContainText(/B$/);
  await expect(page.getByText("This process only. Nothing here is sent on.")).toBeVisible();
  const results = await new AxeBuilder({ page }).analyze();
  expect(results.violations).toEqual([]);
});

test("an alert card can be dismissed and stays accessible", async ({ page }) => {
  await page.route("**/alerts", async (route) => {
    if (route.request().method() !== "GET") {
      await route.fallback();
      return;
    }
    await route.fulfill({
      json: {
        items: [
          {
            kind: "database_error",
            title: "Database error",
            detail: "The house database reported an error. Nothing was sent.",
          },
        ],
      },
    });
  });
  await page.route("**/alerts/database_error/dismiss", async (route) => {
    await route.fulfill({ json: { items: [] } });
  });
  await page.goto("/");
  const card = page.locator("[data-alert='database_error']");
  await expect(card.getByRole("heading", { name: "Database error" })).toBeVisible();
  await expect(card.getByText("Nothing was sent.")).toBeVisible();
  const results = await new AxeBuilder({ page }).analyze();
  expect(results.violations).toEqual([]);
  await card.getByRole("button", { name: "Dismiss Database error" }).click();
  await expect(card).toHaveCount(0);
});

test("voice fills the box with a fake transcription and does not add until asked", async ({ page }) => {
  await installVoice(page);
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/");
  const mic = page.getByRole("button", { name: "Record a line" });
  await expect(mic).toBeVisible();
  const box = await mic.boundingBox();
  expect(box?.width).toBeGreaterThanOrEqual(44);
  expect(box?.height).toBeGreaterThanOrEqual(44);
  await mic.click();
  const stop = page.getByRole("button", { name: "Stop recording" });
  await expect(stop).toBeVisible();
  await stop.click();
  await expect(page.getByLabel("Add to the log")).toHaveValue("buy oat milk");
  await expect(page.locator("[data-kind='proposal']")).toHaveCount(0);
  const results = await new AxeBuilder({ page }).analyze();
  expect(results.violations).toEqual([]);
});

async function installVoice(page: Page) {
  await page.addInitScript(() => {
    class FakeRecorder {
      state = "inactive";
      mimeType = "audio/webm";
      ondataavailable: ((event: { data: Blob }) => void) | null = null;
      onstop: (() => void) | null = null;
      start() {
        this.state = "recording";
      }
      stop() {
        this.state = "inactive";
        const blob = new Blob([new Uint8Array([1, 2, 3])], { type: "audio/webm" });
        this.ondataavailable?.({ data: blob });
        this.onstop?.();
      }
    }
    Object.defineProperty(window, "MediaRecorder", { configurable: true, value: FakeRecorder });
    const mediaDevices = {
      getUserMedia: async () => ({ getTracks: () => [{ stop() {} }] }),
    };
    Object.defineProperty(navigator, "mediaDevices", { configurable: true, value: mediaDevices });
  });
  await page.route("**/system/facts", async (route) => {
    const response = await route.fetch();
    const json = await response.json();
    json.voice_input = "on";
    await route.fulfill({ json });
  });
  await page.route("**/agent", async (route) => {
    const url = new URL(route.request().url());
    if (route.request().method() !== "GET" || url.pathname !== "/agent") {
      await route.fallback();
      return;
    }
    const response = await route.fetch();
    const json = await response.json();
    json.enabled = true;
    json.reachable = true;
    await route.fulfill({ json });
  });
  await page.route("**/voice/transcribe", async (route) => {
    await route.fulfill({ json: { text: "buy oat milk" } });
  });
  await page.route("**/agent/feed", async (route) => {
    await route.fulfill({ status: 500, json: { detail: "Add was not pressed." } });
  });
}
