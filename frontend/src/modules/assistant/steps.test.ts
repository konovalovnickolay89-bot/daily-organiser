import { describe, expect, it } from "vitest";
import { noteStep, orderedSteps } from "./steps";

describe("assistant steps", () => {
  it("settles on done and drops a failure", () => {
    const steps = noteStep(noteStep(["received"], "failed"), "done");
    expect(steps).toEqual(["received", "done"]);
    expect(orderedSteps(steps)).toEqual(["received", "done"]);
  });
});
