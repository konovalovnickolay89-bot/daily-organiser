import { expect, test } from "@playwright/test";

test.beforeEach(async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 960 });
});

test("the rail stays 76px and home keeps three columns on an 8px gap", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();

  const rail = page.getByRole("navigation", { name: "House" });
  const railBox = await rail.boundingBox();
  expect(railBox?.width).toBe(76);

  const grid = await page.locator(".cards").evaluate((el) => {
    const style = getComputedStyle(el);
    return {
      columns: style.gridTemplateColumns.split(" ").filter(Boolean).length,
      gap: style.columnGap,
    };
  });
  expect(grid.columns).toBe(3);
  expect(grid.gap).toBe("24px");

  const card = await page.locator(".card").first().evaluate((el) => {
    const style = getComputedStyle(el);
    return {
      paddingTop: style.paddingTop,
      paddingRight: style.paddingRight,
      paddingBottom: style.paddingBottom,
      paddingLeft: style.paddingLeft,
      radius: style.borderTopLeftRadius,
      border: style.borderTopWidth,
    };
  });
  for (const value of [card.paddingTop, card.paddingRight, card.paddingBottom, card.paddingLeft]) {
    expect(Number.parseFloat(value) % 8).toBe(0);
  }
  expect(card.radius).toBe("12px");
  expect(card.border).toBe("1px");
  const buttonRadius = await page.locator(".rail button").first().evaluate((el) => getComputedStyle(el).borderTopLeftRadius);
  expect(buttonRadius).toBe(card.radius);
});

test("Proposed changes and Decisions share one header style", async ({ page }) => {
  await page.goto("/");
  const proposed = page.getByRole("heading", { name: "Proposed changes" });
  const decisions = page.getByRole("heading", { name: "Decisions" });
  await expect(proposed).toBeVisible();
  await expect(decisions).toBeVisible();

  const metrics = async (heading: ReturnType<typeof page.getByRole>) =>
    heading.evaluate((el) => {
      const style = getComputedStyle(el);
      const section = el.closest("[data-section-header]");
      const rule = section ? getComputedStyle(section) : null;
      return {
        size: style.fontSize,
        family: style.fontFamily,
        weight: style.fontWeight,
        divided: section?.getAttribute("data-section-header"),
        rule: rule?.borderTopWidth,
        pad: rule?.paddingTop,
      };
    });

  expect(await metrics(proposed)).toEqual(await metrics(decisions));
});

test("the house date uses the mono token", async ({ page }) => {
  await page.goto("/");
  const date = page.locator("[data-token=mono]");
  await expect(date).toBeVisible();
  const family = await date.evaluate((el) => getComputedStyle(el).fontFamily);
  expect(family.toLowerCase()).toContain("ibm plex mono");
});
