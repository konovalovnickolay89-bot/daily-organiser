import { describe, expect, it } from "vitest";
import { catchUpFallbackMarker } from "./catchup";

describe("catchUpFallbackMarker", () => {
  it("marks only the brief fallback", () => {
    expect(catchUpFallbackMarker("brief")).toBe("Fallback");
    expect(catchUpFallbackMarker("overdue")).toBe("");
    expect(catchUpFallbackMarker("due_today")).toBe("");
    expect(catchUpFallbackMarker(null)).toBe("");
  });
});
