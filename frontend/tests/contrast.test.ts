import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

function channel(value: number): number {
  const scaled = value / 255;
  return scaled <= 0.04045 ? scaled / 12.92 : ((scaled + 0.055) / 1.055) ** 2.4;
}

function luminance(hex: string): number {
  const raw = hex.replace("#", "");
  const red = channel(parseInt(raw.slice(0, 2), 16));
  const green = channel(parseInt(raw.slice(2, 4), 16));
  const blue = channel(parseInt(raw.slice(4, 6), 16));
  return 0.2126 * red + 0.7152 * green + 0.0722 * blue;
}

function contrast(foreground: string, background: string): number {
  const lighter = Math.max(luminance(foreground), luminance(background));
  const darker = Math.min(luminance(foreground), luminance(background));
  return (lighter + 0.05) / (darker + 0.05);
}

function token(block: string, name: string): string {
  const match = block.match(new RegExp(`${name}:\\s*(#[0-9a-fA-F]{6})`));
  if (!match) throw new Error(`Missing ${name}`);
  return match[1];
}

const css = readFileSync(resolve(process.cwd(), "src/styles.css"), "utf8");
const [evening, morning] = css.split('html[data-theme="morning"]');

describe("theme contrast", () => {
  it("keeps body text at WCAG 2.1 AA on both themes", () => {
    const pairs: Array<[string, string, string]> = [
      [token(evening, "--cream"), token(evening, "--canvas"), "evening cream"],
      [token(evening, "--cream-dim"), token(evening, "--canvas"), "evening muted"],
      [token(evening, "--ink-card"), token(evening, "--card"), "evening ink"],
      [token(evening, "--muted-card"), token(evening, "--card"), "evening muted card"],
      [token(evening, "--accent-ink"), token(evening, "--card"), "evening accent ink"],
      [token(evening, "--danger-card"), token(evening, "--card"), "evening danger"],
      [token(evening, "--success"), token(evening, "--card"), "evening success"],
      [token(evening, "--success-canvas"), token(evening, "--canvas"), "evening success on canvas"],
      [token(morning, "--cream"), token(morning, "--canvas"), "morning cream"],
      [token(morning, "--cream-dim"), token(morning, "--canvas"), "morning muted"],
      [token(morning, "--ink-card"), token(morning, "--card"), "morning ink"],
      [token(morning, "--muted-card"), token(morning, "--card"), "morning muted card"],
      [token(morning, "--accent-ink"), token(morning, "--card"), "morning accent ink"],
      [token(morning, "--success"), token(morning, "--card"), "morning success"],
      [token(morning, "--success-canvas"), token(morning, "--canvas"), "morning success on canvas"],
    ];
    for (const [foreground, background, label] of pairs) {
      expect(contrast(foreground, background), label).toBeGreaterThanOrEqual(4.5);
    }
  });
});
