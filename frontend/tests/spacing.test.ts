import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, resolve } from "node:path";
import { describe, expect, it } from "vitest";

const SRC = resolve(process.cwd(), "src");

function files(dir: string): string[] {
  const found: string[] = [];
  for (const name of readdirSync(dir)) {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) found.push(...files(path));
    else if (name.endsWith(".ts") || name.endsWith(".tsx")) found.push(path);
  }
  return found;
}

/** Layout utilities whose pixel value must sit on the 8px grid. Touch size stays 44px. */
const SPACING_PX =
  /(?:^|[\s"'`])(?:[a-z0-9-]+:)*-?(?:p|px|py|pt|pr|pb|pl|m|mx|my|mt|mr|mb|ml|gap(?:-x|-y)?|inset|top|right|bottom|left|w|h|min-w|min-h|max-w|max-h|basis)-\[(\d+)px\]/g;

const OFF_STEP =
  /(?:^|[\s"'`])(?:[a-z0-9-]+:)*-?(?:p|px|py|pt|pr|pb|pl|m|mx|my|mt|mr|mb|ml|gap(?:-x|-y)?)-(?:0\.5|1\.5|2\.5|3\.5|3|5|7|9|11)(?!\d)/g;

describe("8px spacing", () => {
  it("keeps layout spacing on the 8px grid", () => {
    const problems: string[] = [];
    for (const path of files(SRC)) {
      const text = readFileSync(path, "utf8");
      const relative = path.slice(SRC.length + 1);
      for (const match of text.matchAll(SPACING_PX)) {
        const px = Number(match[1]);
        if (px % 8 !== 0) problems.push(`${relative}: ${px}px`);
      }
      for (const match of text.matchAll(OFF_STEP)) {
        problems.push(`${relative}: ${match[0].trim()}`);
      }
    }
    expect(problems).toEqual([]);
  });

  it("keeps the mono, radius, and rail tokens", () => {
    const css = readFileSync(resolve(SRC, "styles.css"), "utf8");
    expect(css).toContain('--mono: "IBM Plex Mono"');
    expect(css).toContain("--radius: 32px");
    expect(css).toContain("--radius-inset: 24px");
    expect(css).toContain("--radius-pill: 999px");
    expect(css).toContain("--radius-rail: 12px");
    expect(css).toContain("--tube-mid: #d39a4e");
    expect(css).toContain("--tube-deep: #6b3f14");
    expect(css).toContain("--rail: 76px");
    expect(css).toContain("padding: 40px 32px 72px");
    expect(css).toContain("padding: 48px 48px 72px");
    expect(css).toContain("max(24px, env(safe-area-inset-left))");
    expect(css).toContain("max(24px, env(safe-area-inset-right))");
    const tailwind = readFileSync(resolve(process.cwd(), "tailwind.config.js"), "utf8");
    expect(tailwind).toContain('mono: ["var(--mono)"]');
    expect(tailwind).toContain('house: "var(--radius)"');
    expect(tailwind).toContain('inset: "var(--radius-inset)"');
    expect(tailwind).toContain('pill: "var(--radius-pill)"');
    expect(tailwind).toContain('rail: "var(--radius-rail)"');
    expect(tailwind).toContain('rail: "var(--rail)"');
  });
});
