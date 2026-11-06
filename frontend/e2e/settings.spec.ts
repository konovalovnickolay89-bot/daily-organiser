import { expect, test } from "@playwright/test";

test("settings for each feature are on the card", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Settings" }).click();
  const card = page.locator("[data-panel='settings']");
  await expect(card.getByRole("heading", { name: "Playlist" })).toBeVisible();
  await expect(card.getByText("The playlist stays hidden until the source is hearthis.")).toBeVisible();
  await expect(card.getByRole("switch", { name: "Playlist" })).toBeDisabled();
  await expect(card.getByRole("heading", { name: "Alerts and webhooks" })).toBeVisible();
  await expect(card.getByRole("heading", { name: "Voice" })).toBeVisible();
  await expect(card.getByText("The microphone stays off until voice input is turned on.")).toBeVisible();
  await expect(card.getByRole("switch", { name: "Microphone" })).toBeDisabled();
  await expect(card.getByRole("heading", { name: "X limits" })).toBeVisible();
  await expect(card.getByText(/X stays off until X_ENABLED is set/)).toBeVisible();
  await expect(card.getByRole("heading", { name: "Agent context" })).toBeVisible();
  await expect(card.getByRole("heading", { name: "Docs" })).toBeVisible();
  await expect(card.getByText("Docs are off.")).toBeVisible();
  await expect(card.getByRole("heading", { name: "X", exact: true })).toBeVisible();
  await expect(card.getByRole("heading", { name: "Status" })).toBeVisible();
  await expect(card.locator("[data-status='service-mistral']")).toBeVisible();
  await expect(card.locator("[data-status='service-voxtral']")).toBeVisible();
  await expect(card.locator("[data-status='service-google']")).toBeVisible();
  await expect(card.locator("[data-status='service-tfl']")).toBeVisible();
  await expect(card.locator("[data-status='service-x']")).toBeVisible();
  await expect(card.locator("[data-status='service-hearthis']")).toBeVisible();

  const cap = card.getByLabel("Daily cap");
  const started = await cap.inputValue();
  await cap.fill("41");
  await card.getByRole("button", { name: "Save X limits" }).click();
  await expect(cap).toHaveValue("41");
  await page.reload();
  await page.getByRole("button", { name: "Settings" }).click();
  await expect(page.locator("[data-panel='settings']").getByLabel("Daily cap")).toHaveValue("41");
  await page.locator("[data-panel='settings']").getByLabel("Daily cap").fill(started);
  await page.locator("[data-panel='settings']").getByRole("button", { name: "Save X limits" }).click();
  await expect(page.locator("[data-panel='settings']").getByLabel("Daily cap")).toHaveValue(started);
});

test("memory search has an empty state", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Settings" }).click();
  const memory = page.locator("[data-screen='memory']");
  await memory.getByRole("searchbox", { name: "Search memory" }).fill("no-such-memory");
  await expect(memory.getByText("Nothing matches.")).toBeVisible();
});
