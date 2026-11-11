import { readFileSync } from "node:fs";
import { expect, test, type Page } from "@playwright/test";

test.beforeEach(async ({ page }) => {
  await showTheBox(page);
});

test("remember, apply, recall, forget and export", async ({ page }) => {
  const stamp = Date.now();
  const milk = `the cupboard ${stamp} holds the spare bowls`;
  const tea = `the cupboard ${stamp} holds the tea towels`;

  await page.goto("/");
  await page.getByRole("button", { name: "Proposed changes" }).click();
  await page.getByLabel("Add to the log").fill(`remember ${milk}`);
  await page.locator("[data-module='assistant']").getByRole("button", { name: "Add", exact: true }).click();
  await page.getByRole("button", { name: "Decisions" }).click();
  const remember = page.locator("[data-kind='proposal']", { hasText: `Remember: ${milk}` });
  await expect(remember).toBeVisible();
  await page.getByRole("button", { name: "Settings", exact: true }).click();
  const memory = page.locator("[data-screen='memory']");
  await expect(page.getByRole("heading", { name: "Memory" })).toBeVisible();
  await expect(memory.getByText(milk)).toHaveCount(0);

  await page.getByRole("button", { name: "Home" }).click();
  await remember.getByRole("button", { name: "Apply" }).click();
  await expect(page.getByText(`Applied: Remember: ${milk}`)).toBeVisible();

  await page.getByRole("button", { name: "Settings", exact: true }).click();
  await expect(memory.getByText(milk)).toBeVisible();
  await memory.getByRole("searchbox", { name: "Search memory" }).fill(String(stamp));
  await expect(memory.getByText(milk)).toBeVisible();
  await memory.getByRole("searchbox", { name: "Search memory" }).fill("no-such-memory");
  await expect(memory.getByText("Nothing matches.")).toBeVisible();
  await memory.getByRole("searchbox", { name: "Search memory" }).fill(String(stamp));
  const row = memory.locator("[data-memory]", { hasText: milk });
  await row.getByRole("button", { name: "Pin" }).click();
  await expect(row.getByRole("button", { name: "Unpin" })).toHaveAttribute("aria-pressed", "true");

  await page.getByRole("button", { name: "Home" }).click();
  await page.getByRole("button", { name: "Proposed changes" }).click();
  await page.getByLabel("Add to the log").fill(`remember ${tea}`);
  await page.locator("[data-module='assistant']").getByRole("button", { name: "Add", exact: true }).click();
  await page.getByRole("button", { name: "Decisions" }).click();
  const second = page.locator("[data-kind='proposal']", { hasText: `Remember: ${tea}` });
  await expect(second.getByText("Used 1 memory")).toBeVisible();
  await second.getByRole("button", { name: "Apply" }).click();

  await page.getByRole("button", { name: "Proposed changes" }).click();
  await page.getByLabel("Add to the log").fill(`forget cupboard ${stamp}`);
  await page.locator("[data-module='assistant']").getByRole("button", { name: "Add", exact: true }).click();
  await page.getByRole("button", { name: "Decisions" }).click();
  const forget = page.locator("[data-kind='proposal']", { hasText: `Forget: cupboard ${stamp}` });
  await expect(forget.getByRole("checkbox", { name: milk })).toBeChecked();
  await expect(forget.getByRole("checkbox", { name: tea })).toBeChecked();
  await forget.getByRole("checkbox", { name: tea }).uncheck();
  await forget.getByRole("button", { name: "Apply" }).click();

  await page.getByRole("button", { name: "Settings", exact: true }).click();
  await memory.getByRole("searchbox", { name: "Search memory" }).fill(String(stamp));
  await expect(memory.getByText(milk)).toHaveCount(0);
  await expect(memory.getByText(tea)).toBeVisible();

  const downloadPromise = page.waitForEvent("download");
  await memory.getByRole("button", { name: "Export memory" }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe("memory.json");
  const exported = JSON.parse(readFileSync(await download.path(), "utf8"));
  const texts = exported.items.map((item: { text: string }) => item.text);
  expect(texts).toContain(tea);
  expect(texts).not.toContain(milk);
  expect(JSON.stringify(exported)).not.toContain("embedding");

  const kept = memory.locator("[data-memory]", { hasText: tea });
  await kept.getByRole("button", { name: "Forget" }).click();
  await expect(kept.getByText(`Forget “${tea}”?`)).toBeVisible();
  await kept.getByRole("button", { name: "Keep" }).click();
  await expect(memory.getByText(tea)).toBeVisible();
  await kept.getByRole("button", { name: "Forget" }).click();
  await kept.getByRole("button", { name: "Forget" }).click();
  await expect(memory.getByText(tea)).toHaveCount(0);
});

test("a stamped line is the one recalled when similar lines already exist", async ({ page, request }) => {
  const stamp = Date.now();
  const milk = `the cupboard ${stamp} holds the spare bowls`;
  const tea = `the cupboard ${stamp} holds the tea towels`;
  expect((await request.post("/memory", { data: { kind: "fact", text: milk } })).ok()).toBeTruthy();
  for (let index = 0; index < 12; index += 1) {
    const created = await request.post("/memory", {
      data: { kind: "fact", text: `the cupboard holds the spare pantry${stamp} ${index}` },
    });
    expect(created.ok()).toBeTruthy();
  }

  await page.goto("/");
  await page.getByRole("button", { name: "Proposed changes" }).click();
  await page.getByLabel("Add to the log").fill(`remember ${tea}`);
  await page.locator("[data-module='assistant']").getByRole("button", { name: "Add", exact: true }).click();
  await page.getByRole("button", { name: "Decisions" }).click();
  const second = page.locator("[data-kind='proposal']", { hasText: `Remember: ${tea}` });
  await expect(second.getByText("Used 1 memory")).toBeVisible();
});

async function showTheBox(page: Page) {
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
}
