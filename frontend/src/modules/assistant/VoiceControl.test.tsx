import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { VoiceControl } from "./VoiceControl";

const getHouseFacts = vi.fn();
const transcribeAudio = vi.fn();

vi.mock("../../api/system", () => ({
  getHouseFacts: () => getHouseFacts(),
}));

vi.mock("../../api/voice", () => ({
  transcribeAudio: (blob: Blob) => transcribeAudio(blob),
}));

class FakeRecorder {
  state = "inactive";
  mimeType = "audio/webm";
  ondataavailable: ((event: { data: Blob }) => void) | null = null;
  onstop: (() => void) | null = null;
  start() {
    this.state = "recording";
  }
  stop() {
    this.state = "inactive";
    this.ondataavailable?.({ data: new Blob(["clip"], { type: "audio/webm" }) });
    this.onstop?.();
  }
}

describe("Voice control", () => {
  const onText = vi.fn();
  const onError = vi.fn();

  beforeEach(() => {
    cleanup();
    onText.mockReset();
    onError.mockReset();
    getHouseFacts.mockReset();
    transcribeAudio.mockReset();
    vi.stubGlobal("MediaRecorder", FakeRecorder);
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it("stays hidden when voice is off", async () => {
    getHouseFacts.mockResolvedValue({ voice_input: "off" });
    render(<VoiceControl disabled={false} onText={onText} onError={onError} />);
    await waitFor(() => expect(getHouseFacts).toHaveBeenCalled());
    expect(screen.queryByRole("button", { name: "Record a line" })).toBeNull();
  });

  it("records, stops, and drops text into the box without saving", async () => {
    getHouseFacts.mockResolvedValue({ voice_input: "on" });
    transcribeAudio.mockResolvedValue({ text: "buy oat milk" });
    const getUserMedia = vi.fn(async () => ({ getTracks: () => [{ stop() {} }] }));
    Object.defineProperty(navigator, "mediaDevices", { configurable: true, value: { getUserMedia } });
    render(<VoiceControl disabled={false} onText={onText} onError={onError} />);
    const record = await screen.findByRole("button", { name: "Record a line" });
    expect(record.className).toContain("min-h-11");
    expect(record.className).toContain("min-w-11");
    expect(record.className).not.toContain("animate-");
    fireEvent.click(record);
    const stop = await screen.findByRole("button", { name: "Stop recording" });
    expect(stop.getAttribute("aria-pressed")).toBe("true");
    fireEvent.click(stop);
    await waitFor(() => expect(onText).toHaveBeenCalledWith("buy oat milk"));
    expect(transcribeAudio).toHaveBeenCalledTimes(1);
    const blob = transcribeAudio.mock.calls[0][0] as Blob;
    expect(blob).toBeInstanceOf(Blob);
  });

  it("stops on its own at 30 seconds", async () => {
    vi.useFakeTimers();
    getHouseFacts.mockResolvedValue({ voice_input: "on" });
    transcribeAudio.mockResolvedValue({ text: "put the bins out" });
    const getUserMedia = vi.fn(async () => ({ getTracks: () => [{ stop() {} }] }));
    Object.defineProperty(navigator, "mediaDevices", { configurable: true, value: { getUserMedia } });
    render(<VoiceControl disabled={false} onText={onText} onError={onError} />);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });
    const record = screen.getByRole("button", { name: "Record a line" });
    await act(async () => {
      fireEvent.click(record);
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(screen.getByRole("button", { name: "Stop recording" })).toBeTruthy();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(30_000);
    });
    expect(onText).toHaveBeenCalledWith("put the bins out");
  });

  it("says when the microphone is blocked", async () => {
    getHouseFacts.mockResolvedValue({ voice_input: "on" });
    const getUserMedia = vi.fn(async () => Promise.reject(new Error("denied")));
    Object.defineProperty(navigator, "mediaDevices", { configurable: true, value: { getUserMedia } });
    render(<VoiceControl disabled={false} onText={onText} onError={onError} />);
    fireEvent.click(await screen.findByRole("button", { name: "Record a line" }));
    await waitFor(() =>
      expect(onError).toHaveBeenCalledWith("The microphone is blocked. Allow it in the browser, or type the line."),
    );
    expect(onText).not.toHaveBeenCalled();
  });
});
