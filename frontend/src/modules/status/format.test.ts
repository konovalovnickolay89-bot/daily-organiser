import { describe, expect, it } from "vitest";
import { formatBytes, formatHouseTime } from "./format";

describe("status format", () => {
  it("formats a database size", () => {
    expect(formatBytes(null)).toBe("Unknown");
    expect(formatBytes(12)).toBe("12 B");
    expect(formatBytes(1536)).toBe("1.5 KB");
    expect(formatBytes(2 * 1024 * 1024)).toBe("2.0 MB");
  });

  it("formats a house time, or says not yet", () => {
    expect(formatHouseTime(null)).toBe("Not yet");
    expect(formatHouseTime("not-a-time")).toBe("Not yet");
    expect(formatHouseTime("2026-11-06T08:05:00+00:00")).toBe("6 Nov, 08:05");
  });
});
