import { describe, expect, it } from "vitest";
import { formatBytes, formatHouseTime, formatXLine } from "./format";

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

  it("formats the X credits and rate line", () => {
    expect(formatXLine(undefined)).toBe("Off");
    expect(formatXLine({ enabled: false, connected: false, credits_remaining: null, rate_remaining: null, backing_off: false })).toBe("Off");
    expect(formatXLine({ enabled: true, connected: false, credits_remaining: null, rate_remaining: null, backing_off: false })).toBe(
      "Not connected",
    );
    expect(
      formatXLine({ enabled: true, connected: true, credits_remaining: 120, rate_remaining: 45, backing_off: false }),
    ).toBe("120 credits · 45 left");
    expect(
      formatXLine({
        enabled: true,
        connected: true,
        credits_remaining: 120,
        rate_remaining: 45,
        backing_off: false,
        poll_paused: true,
      }),
    ).toBe("Reading paused");
    expect(
      formatXLine({ enabled: true, connected: true, credits_remaining: 120, rate_remaining: 45, backing_off: true }),
    ).toBe("Backing off");
    expect(
      formatXLine({
        enabled: true,
        connected: true,
        credits_remaining: null,
        rate_remaining: null,
        backing_off: true,
        attention: "auth",
      }),
    ).toBe("Reconnect");
  });
});
