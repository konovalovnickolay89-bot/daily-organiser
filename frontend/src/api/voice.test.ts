import { afterEach, describe, expect, it, vi } from "vitest";
import { recordingName, transcribeAudio } from "./voice";

describe("recording name", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("follows the base type and ignores a codecs parameter", () => {
    expect(recordingName(new Blob(["a"], { type: "audio/mp4" }))).toBe("line.mp4");
    expect(recordingName(new Blob(["a"], { type: "audio/mp4;codecs=mp4a.40.2" }))).toBe("line.mp4");
    expect(recordingName(new Blob(["a"], { type: "audio/webm;codecs=opus" }))).toBe("line.webm");
    expect(recordingName(new Blob(["a"], { type: "" }))).toBe("line.bin");
  });

  it("uploads under that name", async () => {
    const fetchMock = vi.fn(async (_url: string, init?: RequestInit) => {
      return new Response(JSON.stringify({ text: "Test data: oat milk" }), { status: 200, headers: init?.headers });
    });
    vi.stubGlobal("fetch", fetchMock);
    await transcribeAudio(new Blob(["clip"], { type: "audio/mp4;codecs=mp4a.40.2" }));
    const init = fetchMock.mock.calls[0]?.[1];
    const body = init?.body as FormData;
    const file = body.get("file") as File;
    expect(file.name).toBe("line.mp4");
  });
});
