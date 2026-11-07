import { afterEach, describe, expect, it } from "vitest";
import { previewShown, setPreviewShown } from "./previewStore";

describe("reminder preview choice", () => {
  afterEach(() => window.localStorage.clear());

  it("is shown until this browser hides it", () => {
    window.localStorage.clear();
    expect(previewShown()).toBe(true);
    setPreviewShown(false);
    expect(previewShown()).toBe(false);
    setPreviewShown(true);
    expect(previewShown()).toBe(true);
  });
});
