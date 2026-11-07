import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

test("status panel shows health, version, and the database", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Settings" }).click();
  await expect(page.getByRole("heading", { name: "Status", exact: true })).toBeVisible();
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
  let uploads = 0;
  await installVoice(page, () => {
    uploads += 1;
  });
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/");
  await page.getByRole("button", { name: "Proposed changes" }).click();
  const line = page.getByLabel("Add to the log");
  const voice = page.locator("[data-voice='mic']");
  const add = page.locator("[data-module='assistant']").getByRole("button", { name: "Add", exact: true });
  await line.fill("oats typed");
  const mic = page.getByRole("button", { name: "Start recording" });
  await expect(mic).toBeVisible();
  await expect(voice.locator("#voice-help")).toHaveText(
    "Up to 30 seconds and 512 KB. Nothing is sent until you stop and transcribe. Audio is not kept.",
  );
  const box = await mic.boundingBox();
  expect(box?.width).toBeGreaterThanOrEqual(44);
  expect(box?.height).toBeGreaterThanOrEqual(44);

  await mic.focus();
  await page.keyboard.press("Enter");
  const stop = page.getByRole("button", { name: "Stop and transcribe" });
  const cancel = page.getByRole("button", { name: "Cancel recording" });
  await expect(stop).toBeVisible();
  await expect(cancel).toBeVisible();
  await expect(voice).toHaveAttribute("data-voice-phase", "recording");
  await expect(voice.getByText("Recording", { exact: true })).toBeVisible();
  const inputBox = await line.boundingBox();
  const voiceBox = await voice.boundingBox();
  expect(inputBox && voiceBox && voiceBox.y - (inputBox.y + inputBox.height)).toBeGreaterThanOrEqual(24);
  await expect(voice.locator("#voice-help")).toContainText("Stop and transcribe sends this clip to Mistral.");
  await expect(voice.locator("#voice-help")).toContainText("At 30 seconds it is sent on its own.");
  await expect(voice.locator("#voice-help")).toContainText("Cancel recording does not upload.");
  await expect(add).toBeDisabled();
  await page.keyboard.press("Escape");
  await expect(voice).toHaveAttribute("data-voice-phase", "idle");
  await expect(voice.getByText("Cancelled. Nothing was uploaded. The line is unchanged.", { exact: true })).toBeVisible();
  await expect(line).toHaveValue("oats typed");
  expect(uploads).toBe(0);

  await page.getByRole("button", { name: "Start recording" }).click();
  await page.getByRole("button", { name: "Stop and transcribe" }).click();
  await expect(line).toHaveValue("buy oat milk");
  await expect(voice.locator("#voice-help")).toHaveText("Words are in the line. Edit them, then press Add. Nothing is added until then.");
  await expect(add).toBeEnabled();
  await expect(page.locator("[data-kind='proposal']")).toHaveCount(0);
  expect(uploads).toBe(1);
  const results = await new AxeBuilder({ page }).analyze();
  expect(results.violations).toEqual([]);
});

test("voice controls stay labelled on a phone width", async ({ page }) => {
  await installVoice(page);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/");
  await page.getByRole("button", { name: "Proposed changes" }).click();
  const mic = page.getByRole("button", { name: "Start recording" });
  await expect(mic).toBeVisible();
  await mic.click();
  const stop = page.getByRole("button", { name: "Stop and transcribe" });
  await expect(stop).toBeVisible();
  await expect(page.getByRole("button", { name: "Cancel recording" })).toBeVisible();
  const stopBox = await stop.boundingBox();
  expect(stopBox?.height).toBeGreaterThanOrEqual(44);
  const wide = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1);
  expect(wide).toBe(false);
  const results = await new AxeBuilder({ page }).analyze();
  expect(results.violations).toEqual([]);
});

async function installVoice(page: Page, onUpload?: () => void) {
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
    onUpload?.();
    await route.fulfill({ json: { text: "buy oat milk" } });
  });
  await page.route("**/agent/feed", async (route) => {
    await route.fulfill({ status: 500, json: { detail: "Add was not pressed." } });
  });
}
