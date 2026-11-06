import { useEffect, useRef, useState } from "react";
import { getHouseFacts } from "../../api/system";
import { transcribeAudio } from "../../api/voice";
import { cx, ghost } from "../../arrival/ui";
import { asError } from "../../lib/errors";

const MAX_MS = 30_000;

type VoiceControlProps = {
  disabled: boolean;
  onText: (text: string) => void;
  onError: (message: string | null) => void;
};

/**
 * Mic on Smart Add. Hidden unless the house turned voice on.
 * The clip stays in memory, stops at 30 seconds, and only fills the box.
 */
export function VoiceControl({ disabled, onText, onError }: VoiceControlProps) {
  const [enabled, setEnabled] = useState(false);
  const [phase, setPhase] = useState<"idle" | "recording" | "sending">("idle");
  const recorder = useRef<MediaRecorder | null>(null);
  const stream = useRef<MediaStream | null>(null);
  const timer = useRef<number | null>(null);
  const chunks = useRef<Blob[]>([]);

  useEffect(() => {
    let cancelled = false;
    getHouseFacts()
      .then((facts) => {
        if (!cancelled) setEnabled(facts.voice_input === "on");
      })
      .catch(() => {
        if (!cancelled) setEnabled(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    return () => {
      if (timer.current !== null) window.clearTimeout(timer.current);
      stream.current?.getTracks().forEach((track) => track.stop());
    };
  }, []);

  if (!enabled) return null;

  function stopTracks() {
    stream.current?.getTracks().forEach((track) => track.stop());
    stream.current = null;
  }

  function stop() {
    if (timer.current !== null) {
      window.clearTimeout(timer.current);
      timer.current = null;
    }
    const rec = recorder.current;
    if (rec && rec.state !== "inactive") rec.stop();
  }

  async function finish(blob: Blob) {
    setPhase("sending");
    try {
      const result = await transcribeAudio(blob);
      onText(result.text);
      onError(null);
    } catch (err: unknown) {
      onError(asError(err).message);
    } finally {
      setPhase("idle");
    }
  }

  async function start() {
    onError(null);
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") {
      onError("This browser has no microphone.");
      return;
    }
    let media: MediaStream;
    try {
      media = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch {
      onError("The microphone is blocked. Allow it in the browser, or type the line.");
      return;
    }
    stream.current = media;
    chunks.current = [];
    let rec: MediaRecorder;
    try {
      rec = new MediaRecorder(media);
    } catch {
      stopTracks();
      onError("This browser has no microphone.");
      return;
    }
    recorder.current = rec;
    rec.ondataavailable = (event) => {
      if (event.data.size > 0) chunks.current.push(event.data);
    };
    rec.onstop = () => {
      const blob = new Blob(chunks.current, { type: rec.mimeType || "audio/webm" });
      chunks.current = [];
      stopTracks();
      if (blob.size === 0) {
        setPhase("idle");
        onError("Nothing was recorded.");
        return;
      }
      void finish(blob);
    };
    rec.start();
    setPhase("recording");
    timer.current = window.setTimeout(() => stop(), MAX_MS);
  }

  const recording = phase === "recording";
  const label = recording ? "Stop recording" : "Record a line";

  return (
    <button
      type="button"
      className={cx(ghost, "motion-reduce:transition-none shrink-0")}
      data-voice="mic"
      aria-label={label}
      aria-pressed={recording}
      disabled={disabled || phase === "sending"}
      onClick={() => {
        if (recording) stop();
        else void start();
      }}
    >
      {phase === "sending" ? "…" : recording ? "Stop" : "Record"}
    </button>
  );
}
