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
      borderColor: style.borderTopColor,
    };
  });
  for (const value of [card.paddingTop, card.paddingRight, card.paddingBottom, card.paddingLeft]) {
    expect(Number.parseFloat(value) % 8).toBe(0);
  }
  expect(card.paddingTop).toBe("48px");
  expect(card.radius).toBe("32px");
  expect(card.border).toBe("3px");
  expect(card.borderColor).toBe("rgb(211, 154, 78)");
  const buttonRadius = await page.locator(".rail button").first().evaluate((el) => getComputedStyle(el).borderTopLeftRadius);
  expect(buttonRadius).toBe("12px");
});

test("a narrow screen keeps the tube, the lighter padding, and no sideways scroll", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  const card = await page.locator(".card").first().evaluate((el) => {
    const style = getComputedStyle(el);
    return { padding: style.paddingTop, radius: style.borderTopLeftRadius, border: style.borderTopWidth };
  });
  expect(card.padding).toBe("32px");
  expect(card.radius).toBe("32px");
  expect(card.border).toBe("3px");
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow).toBeLessThanOrEqual(1);
});

test("keyboard focus stays visible outside the tube", async ({ page }) => {
  await page.goto("/");
  const pause = page.getByRole("button", { name: "Pause" });
  for (let step = 0; step < 12; step += 1) {
    if (await pause.evaluate((el) => el === document.activeElement)) break;
    await page.keyboard.press("Tab");
  }
  await expect(pause).toBeFocused();
  const ring = await pause.evaluate((el) => {
    const style = getComputedStyle(el);
    return { width: style.outlineWidth, offset: style.outlineOffset, color: style.outlineColor, style: style.outlineStyle };
  });
  expect(ring.style).toBe("solid");
  expect(ring.width).toBe("2px");
  expect(ring.offset).toBe("5px");
  expect(ring.color).toBe("rgb(211, 154, 78)");
});

test("inner panels, inputs, and pills use their own radii", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Approvals" }).click();
  const proposal = page.locator("[data-panel='reasoning'] .proposal-card").first();
  await expect(proposal).toBeVisible();
  const panel = await proposal.evaluate((el) => {
    const style = getComputedStyle(el);
    return { radius: style.borderTopLeftRadius, border: style.borderTopWidth };
  });
  expect(panel.radius).toBe("24px");
  expect(panel.border).toBe("2px");
  const panelPad = await proposal.evaluate((el) => getComputedStyle(el).paddingTop);
  expect(panelPad).toBe("24px");

  const notNow = page.getByRole("button", { name: "Not now" }).first();
  const pillRadius = await notNow.evaluate((el) => getComputedStyle(el).borderTopLeftRadius);
  expect(pillRadius).toBe("999px");

  await page.getByRole("button", { name: "Settings" }).click();
  const theme = page.getByRole("radio", { name: "Morning" });
  await expect(theme).toBeVisible();
  const choice = await theme.evaluate((el) => getComputedStyle(el.parentElement as HTMLElement).borderTopLeftRadius);
  expect(choice).toBe("999px");

  const search = page.getByRole("searchbox", { name: "Search memory" });
  const field = await search.evaluate((el) => {
    const style = getComputedStyle(el);
    return { radius: style.borderTopLeftRadius, border: style.borderTopWidth };
  });
  expect(field.radius).toBe("24px");
  expect(field.border).toBe("2px");
  const fieldPad = await search.evaluate((el) => getComputedStyle(el).paddingLeft);
  expect(fieldPad).toBe("24px");
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
