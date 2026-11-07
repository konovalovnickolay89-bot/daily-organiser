import { describe, expect, it } from "vitest";
import { watchValueError } from "./watch";

describe("watch value", () => {
  it("accepts a keyword and a handle", () => {
    expect(watchValueError("keyword", "bins")).toBeNull();
    expect(watchValueError("keyword", "Boiler filter")).toBeNull();
    expect(watchValueError("account", "@HouseBin")).toBeNull();
    expect(watchValueError("account", "house_bin")).toBeNull();
  });

  it("refuses an empty value, a symbol, and a long handle", () => {
    expect(watchValueError("keyword", "  ")).toBe("Add a watch.");
    expect(watchValueError("keyword", "bins!")).toMatch(/plain words/);
    expect(watchValueError("account", "this-handle-is-far-too-long")).toMatch(/up to 15/);
    expect(watchValueError("account", "bad handle")).toMatch(/up to 15/);
  });
});
