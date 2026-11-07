import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { useState } from "react";
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
  static payload: Blob = new Blob(["clip"], { type: "audio/webm" });
  state = "inactive";
  mimeType = "audio/webm";
  ondataavailable: ((event: { data: Blob }) => void) | null = null;
  onstop: (() => void) | null = null;
  start() {
    this.state = "recording";
  }
  stop() {
    this.state = "inactive";
    this.ondataavailable?.({ data: FakeRecorder.payload });
    this.onstop?.();
  }
}

function installMedia(stop = vi.fn()) {
  const getUserMedia = vi.fn(async () => ({ getTracks: () => [{ stop }] }));
  Object.defineProperty(navigator, "mediaDevices", { configurable: true, value: { getUserMedia } });
  return { getUserMedia, stop };
}

function LineBox({ onBusy }: { onBusy?: (busy: boolean) => void }) {
  const [text, setText] = useState("oats typed");
  const [adds, setAdds] = useState(0);
  return (
    <form
      onSubmit={(event) => {
        event.preventDefault();
        setAdds((count) => count + 1);
      }}
    >
      <input aria-label="Add to the log" value={text} onChange={(event) => setText(event.target.value)} />
      <VoiceControl disabled={false} onText={setText} onBusy={onBusy} />
      <button type="submit">Add</button>
      <p data-adds={adds}>{adds}</p>
    </form>
  );
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
    FakeRecorder.payload = new Blob(["clip"], { type: "audio/webm" });
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
    expect(screen.queryByRole("button", { name: "Start recording" })).toBeNull();
    expect(screen.queryByRole("group", { name: "Voice" })).toBeNull();
  });

  it("shows one start action, then stop as the primary and cancel as the discard", async () => {
    getHouseFacts.mockResolvedValue({ voice_input: "on" });
    installMedia();
    render(<VoiceControl disabled={false} onText={onText} onError={onError} />);
    const start = await screen.findByRole("button", { name: "Start recording" });
    expect(start.textContent).toBe("Start recording");
    expect(start.className).toContain("min-h-11");
    expect(start.className).toContain("min-w-11");
    expect(start.className).not.toContain("animate-");
    expect(screen.getByRole("group", { name: "Voice" }).className).toContain("tube-inset");
    expect(screen.getByText(/Nothing is sent until you stop and transcribe/)).toBeTruthy();
    fireEvent.click(start);
    const stop = await screen.findByRole("button", { name: "Stop and transcribe" });
    const cancel = screen.getByRole("button", { name: "Cancel recording" });
    expect(stop.className).toContain("bg-accent");
    expect(cancel.className).toContain("text-[var(--danger)]");
    expect(screen.getByText("Recording")).toBeTruthy();
    expect(screen.getByText("0:00 / 0:30")).toBeTruthy();
    expect(screen.getAllByText(/sends this clip to Mistral/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/does not upload/).length).toBeGreaterThan(0);
    expect(document.activeElement).toBe(stop);
  });

  it("sends on stop, replaces the line, and does not submit until Add", async () => {
    getHouseFacts.mockResolvedValue({ voice_input: "on" });
    transcribeAudio.mockResolvedValue({ text: "buy oat milk" });
    const busy = vi.fn();
    installMedia();
    render(<LineBox onBusy={busy} />);
    fireEvent.click(await screen.findByRole("button", { name: "Start recording" }));
    await screen.findByRole("button", { name: "Stop and transcribe" });
    expect(busy).toHaveBeenCalledWith(true);
    expect(screen.getByText("0")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Stop and transcribe" }));
    await waitFor(() => expect((screen.getByLabelText("Add to the log") as HTMLInputElement).value).toBe("buy oat milk"));
    expect(transcribeAudio).toHaveBeenCalledTimes(1);
    expect(screen.getAllByText(/Edit them, then press Add/).length).toBeGreaterThan(0);
    expect(screen.getByText("0")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Transcribing…" })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Add" }));
    expect(screen.getByText("1")).toBeTruthy();
    await waitFor(() => expect(busy).toHaveBeenCalledWith(false));
  });

  it("cancels without uploading and leaves typed text", async () => {
    getHouseFacts.mockResolvedValue({ voice_input: "on" });
    const { stop } = installMedia();
    render(<LineBox />);
    fireEvent.click(await screen.findByRole("button", { name: "Start recording" }));
    fireEvent.click(await screen.findByRole("button", { name: "Cancel recording" }));
    expect(transcribeAudio).not.toHaveBeenCalled();
    expect(stop).toHaveBeenCalled();
    expect((screen.getByLabelText("Add to the log") as HTMLInputElement).value).toBe("oats typed");
    expect(screen.getByText(/Nothing was uploaded/)).toBeTruthy();
    expect(screen.getByText("0")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Start recording" })).toBeTruthy();
  });

  it("discards on Escape and when the page is hidden", async () => {
    getHouseFacts.mockResolvedValue({ voice_input: "on" });
    installMedia();
    render(<VoiceControl disabled={false} onText={onText} onError={onError} />);
    fireEvent.click(await screen.findByRole("button", { name: "Start recording" }));
    await screen.findByRole("button", { name: "Stop and transcribe" });
    act(() => {
      window.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape" }));
    });
    expect(transcribeAudio).not.toHaveBeenCalled();
    expect(screen.getByText("Cancelled. Nothing was uploaded. The line is unchanged.")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "Start recording" }));
    await screen.findByRole("button", { name: "Stop and transcribe" });
    act(() => {
      Object.defineProperty(document, "visibilityState", { configurable: true, get: () => "hidden" });
      document.dispatchEvent(new Event("visibilitychange"));
    });
    expect(transcribeAudio).not.toHaveBeenCalled();
    expect(screen.getByText(/this page was hidden/)).toBeTruthy();
    Object.defineProperty(document, "visibilityState", { configurable: true, get: () => "visible" });
  });

  it("stops the microphone on unmount without uploading", async () => {
    getHouseFacts.mockResolvedValue({ voice_input: "on" });
    const { stop } = installMedia();
    const view = render(<VoiceControl disabled={false} onText={onText} onError={onError} />);
    fireEvent.click(await screen.findByRole("button", { name: "Start recording" }));
    await screen.findByRole("button", { name: "Stop and transcribe" });
    view.unmount();
    expect(stop).toHaveBeenCalled();
    expect(transcribeAudio).not.toHaveBeenCalled();
    expect(onText).not.toHaveBeenCalled();
  });

  it("stops on its own at 30 seconds and then sends", async () => {
    vi.useFakeTimers();
    getHouseFacts.mockResolvedValue({ voice_input: "on" });
    let resolveText: (value: { text: string }) => void = () => {};
    transcribeAudio.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveText = resolve;
        }),
    );
    installMedia();
    render(<VoiceControl disabled={false} onText={onText} onError={onError} />);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Start recording" }));
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(screen.getByRole("button", { name: "Stop and transcribe" })).toBeTruthy();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(30_000);
    });
    expect(screen.getAllByText(/Reached 30 seconds/).length).toBeGreaterThan(0);
    expect(screen.queryByRole("button", { name: "Cancel recording" })).toBeNull();
    expect(transcribeAudio).toHaveBeenCalledTimes(1);
    await act(async () => {
      resolveText({ text: "put the bins out" });
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(onText).toHaveBeenCalledWith("put the bins out");
  });

  it("refuses a clip over 512 KB before upload", async () => {
    getHouseFacts.mockResolvedValue({ voice_input: "on" });
    FakeRecorder.payload = new Blob([new Uint8Array(512 * 1024 + 1)], { type: "audio/webm" });
    installMedia();
    render(<LineBox />);
    fireEvent.click(await screen.findByRole("button", { name: "Start recording" }));
    fireEvent.click(await screen.findByRole("button", { name: "Stop and transcribe" }));
    expect((await screen.findByRole("alert")).textContent).toBe(
      "That recording is too long. It was not sent. The line is unchanged.",
    );
    expect(transcribeAudio).not.toHaveBeenCalled();
    expect((screen.getByLabelText("Add to the log") as HTMLInputElement).value).toBe("oats typed");
  });

  it("says when the microphone is blocked and keeps the line", async () => {
    getHouseFacts.mockResolvedValue({ voice_input: "on" });
    const getUserMedia = vi.fn(async () => Promise.reject(new DOMException("denied", "NotAllowedError")));
    Object.defineProperty(navigator, "mediaDevices", { configurable: true, value: { getUserMedia } });
    render(<LineBox />);
    fireEvent.click(await screen.findByRole("button", { name: "Start recording" }));
    expect((await screen.findByRole("alert")).textContent).toBe(
      "The microphone is blocked. Allow it in the browser, or type the line. The line is unchanged.",
    );
    expect((screen.getByLabelText("Add to the log") as HTMLInputElement).value).toBe("oats typed");
    expect(screen.getByRole("button", { name: "Start recording" }).hasAttribute("disabled")).toBe(false);
    expect(onText).not.toHaveBeenCalled();
  });

  it("says when the browser has no microphone", async () => {
    getHouseFacts.mockResolvedValue({ voice_input: "on" });
    vi.stubGlobal("MediaRecorder", undefined);
    Object.defineProperty(navigator, "mediaDevices", { configurable: true, value: undefined });
    render(<VoiceControl disabled={false} onText={onText} onError={onError} />);
    fireEvent.click(await screen.findByRole("button", { name: "Start recording" }));
    expect((await screen.findByRole("alert")).textContent).toBe(
      "This browser has no microphone. Type the line instead. The line is unchanged.",
    );
    expect(transcribeAudio).not.toHaveBeenCalled();
  });

  it("reports a network failure without claiming the audio was not sent", async () => {
    getHouseFacts.mockResolvedValue({ voice_input: "on" });
    transcribeAudio.mockRejectedValue(new Error("The house log is not reachable."));
    installMedia();
    render(<LineBox />);
    fireEvent.click(await screen.findByRole("button", { name: "Start recording" }));
    fireEvent.click(await screen.findByRole("button", { name: "Stop and transcribe" }));
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toBe("The house log is not reachable. Nothing was added. The line is unchanged.");
    expect(alert.textContent).not.toMatch(/not sent|not uploaded/i);
    expect((screen.getByLabelText("Add to the log") as HTMLInputElement).value).toBe("oats typed");
    expect(screen.getByRole("button", { name: "Start recording" }).hasAttribute("disabled")).toBe(false);
  });

  it("reports a provider failure and leaves the line", async () => {
    getHouseFacts.mockResolvedValue({ voice_input: "on" });
    transcribeAudio.mockRejectedValue(new Error("Voice could not be transcribed. Nothing was saved."));
    installMedia();
    render(<LineBox />);
    fireEvent.click(await screen.findByRole("button", { name: "Start recording" }));
    fireEvent.click(await screen.findByRole("button", { name: "Stop and transcribe" }));
    expect((await screen.findByRole("alert")).textContent).toBe(
      "Voice could not be transcribed. Nothing was saved. Nothing was added. The line is unchanged.",
    );
    expect((screen.getByLabelText("Add to the log") as HTMLInputElement).value).toBe("oats typed");
    expect(transcribeAudio).toHaveBeenCalledTimes(1);
  });

  it("does not start a second recording while the first is opening", async () => {
    getHouseFacts.mockResolvedValue({ voice_input: "on" });
    let resolveMedia: (stream: { getTracks: () => { stop: () => void }[] }) => void = () => {};
    const getUserMedia = vi.fn(
      () =>
        new Promise((resolve) => {
          resolveMedia = resolve;
        }),
    );
    Object.defineProperty(navigator, "mediaDevices", { configurable: true, value: { getUserMedia } });
    render(<VoiceControl disabled={false} onText={onText} onError={onError} />);
    const start = await screen.findByRole("button", { name: "Start recording" });
    fireEvent.click(start);
    fireEvent.click(screen.getByRole("button", { name: "Starting…" }));
    expect(getUserMedia).toHaveBeenCalledTimes(1);
    await act(async () => {
      resolveMedia({ getTracks: () => [{ stop() {} }] });
    });
    expect(await screen.findByRole("button", { name: "Stop and transcribe" })).toBeTruthy();
  });

  it("drops an in-progress recording when voice is disabled", async () => {
    getHouseFacts.mockResolvedValue({ voice_input: "on" });
    const { stop } = installMedia();
    const view = render(<VoiceControl disabled={false} onText={onText} onError={onError} />);
    fireEvent.click(await screen.findByRole("button", { name: "Start recording" }));
    await screen.findByRole("button", { name: "Stop and transcribe" });
    view.rerender(<VoiceControl disabled onText={onText} onError={onError} />);
    expect(transcribeAudio).not.toHaveBeenCalled();
    expect(stop).toHaveBeenCalled();
    expect(screen.getByText("Recording stopped. Nothing was uploaded.")).toBeTruthy();
  });
});
