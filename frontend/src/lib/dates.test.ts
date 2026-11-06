import { describe, expect, it } from "vitest";
import { dateHasPassedNote } from "./dates";

describe("dateHasPassedNote", () => {
  it("notes a date before the house date", () => {
    expect(dateHasPassedNote("2026-11-05", "2026-11-06")).toBe("That date has passed.");
  });

  it("stays quiet for today, later, or a blank date", () => {
    expect(dateHasPassedNote("2026-11-06", "2026-11-06")).toBe("");
    expect(dateHasPassedNote("2026-11-07", "2026-11-06")).toBe("");
    expect(dateHasPassedNote("", "2026-11-06")).toBe("");
    expect(dateHasPassedNote("soon", "2026-11-06")).toBe("");
  });
});
