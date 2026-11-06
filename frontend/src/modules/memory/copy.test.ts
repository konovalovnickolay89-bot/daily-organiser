import { describe, expect, it } from "vitest";
import { usedMemoriesLabel } from "./copy";

describe("used memories", () => {
  it("stays quiet when none were used", () => {
    expect(usedMemoriesLabel(0)).toBeNull();
    expect(usedMemoriesLabel(null)).toBeNull();
    expect(usedMemoriesLabel(undefined)).toBeNull();
  });

  it("names the count", () => {
    expect(usedMemoriesLabel(1)).toBe("Used 1 memory");
    expect(usedMemoriesLabel(2)).toBe("Used 2 memories");
  });
});
