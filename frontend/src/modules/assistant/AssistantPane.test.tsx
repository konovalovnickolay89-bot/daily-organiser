import { cleanup, render } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AssistantPane } from "./AssistantPane";

vi.mock("./AssistantContext", () => ({
  useAssistant: () => ({
    state: { enabled: true, reachable: true, paused: false, proposals: [] },
    error: null,
    text: "",
    setText: () => {},
    sorting: false,
    enabled: true,
    reachable: true,
    paused: false,
    proposals: [],
    submit: () => undefined,
  }),
}));

vi.mock("../../arrival/view", () => ({
  useView: () => "home",
}));

vi.mock("./VoiceControl", () => ({
  VoiceControl: () => <div data-voice="mic" />,
}));

vi.mock("./AssistantResult", () => ({
  AssistantResult: () => null,
}));

describe("Proposed changes spacing", () => {
  afterEach(() => {
    cleanup();
  });

  it("leaves a gap under the header and above the voice group", () => {
    const view = render(<AssistantPane />);
    const form = view.container.querySelector("form");
    expect(form?.className).toContain("mt-6");
    expect(form?.className).toContain("gap-6");
    expect(form?.querySelector("div")?.className).toContain("gap-4");
  });
});
