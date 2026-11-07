import { useEffect, useRef, useState } from "react";
import { getHouseFacts } from "../../api/system";
import { transcribeAudio } from "../../api/voice";
import { cx, errorText, ghost, inset, kickerMuted, primary } from "../../arrival/ui";
import { asError } from "../../lib/errors";

/** Matches organiser.agent.voice.MAX_BYTES. Checked before any upload. */
const MAX_BYTES = 512 * 1024;
const MAX_MS = 30_000;
const TICK_MS = 250;

type Phase = "idle" | "opening" | "recording" | "transcribing";
type Intent = "transcribe" | "discard";

type VoiceControlProps = {
  disabled: boolean;
  onText: (text: string) => void;
  onError?: (message: string | null) => void;
  /** True while the microphone is opening, recording, or a clip is in flight. */
  onBusy?: (busy: boolean) => void;
};

const IDLE_HELP =
  "Up to 30 seconds and 512 KB. Nothing is sent until you stop and transcribe. Audio is not kept.";
const RECORDING_HELP =
  "Stop and transcribe sends this clip to Mistral. The words replace the line. Cancel recording does not upload. Escape does the same.";
const SENDING_HELP = "Sending this recording to Mistral. Nothing is added until you press Add. Audio is not kept.";
const CAPPED_HELP = "Reached 30 seconds. Sending this recording to Mistral. Nothing is added until you press Add. Audio is not kept.";
const REVIEW_HELP = "Words are in the line. Edit them, then press Add. Nothing is added until then.";
const CANCELLED = "Cancelled. Nothing was uploaded. The line is unchanged.";
const STOPPED = "Recording stopped. Nothing was uploaded.";
const HIDDEN = "Recording stopped because this page was hidden. Nothing was uploaded.";
const KEPT = "Nothing was added. The line is unchanged.";

function clock(ms: number) {
  const seconds = Math.min(30, Math.floor(ms / 1000));
  return `0:${String(seconds).padStart(2, "0")}`;
}

function micMessage(err: unknown) {
  const name = err instanceof DOMException ? err.name : "";
  if (name === "NotFoundError" || name === "NotSupportedError") {
    return "This browser has no microphone. Type the line instead. The line is unchanged.";
  }
  return "The microphone is blocked. Allow it in the browser, or type the line. The line is unchanged.";
}

/** A failure after the upload started must not claim the audio never left. */
function failureMessage(err: unknown) {
  const message = asError(err).message;
  if (message.includes("The line is unchanged.")) return message;
  if (message === "That recording is too long.") return `That recording is too long. ${KEPT}`;
  return `${message} ${KEPT}`;
}

/**
 * Voice on Smart Add. One group, one primary action for the state it is in.
 * Hidden unless the house turned voice on. The clip stays in memory, stops at
 * 30 seconds, and is sent only by Stop and transcribe. Add stays separate.
 */
export function VoiceControl({ disabled, onText, onError, onBusy }: VoiceControlProps) {
  const [enabled, setEnabled] = useState(false);
  const [phase, setPhase] = useState<Phase>("idle");
  const [elapsed, setElapsed] = useState(0);
  const [help, setHelp] = useState(IDLE_HELP);
  const [live, setLive] = useState("");
  const [error, setError] = useState<string | null>(null);
  const recorder = useRef<MediaRecorder | null>(null);
  const stream = useRef<MediaStream | null>(null);
  const timer = useRef<number | null>(null);
  const tick = useRef<number | null>(null);
  const chunks = useRef<Blob[]>([]);
  const elapsedMs = useRef(0);
  const intent = useRef<Intent>("discard");
  const capped = useRef(false);
  const generation = useRef(0);
  const alive = useRef(true);
  const phaseRef = useRef<Phase>("idle");
  const startButton = useRef<HTMLButtonElement | null>(null);
  const stopButton = useRef<HTMLButtonElement | null>(null);
  const statusNode = useRef<HTMLParagraphElement | null>(null);
  const previousPhase = useRef<Phase>("idle");
  const focusAfter = useRef<"start" | "line" | null>(null);
  const haltRef = useRef<(next: Intent, status?: string) => void>(() => {});

  function setPhaseNow(next: Phase) {
    phaseRef.current = next;
    setPhase(next);
  }

  function stopTracks() {
    stream.current?.getTracks().forEach((track) => track.stop());
    stream.current = null;
  }

  function clearClock() {
    if (timer.current !== null) {
      window.clearTimeout(timer.current);
      timer.current = null;
    }
    if (tick.current !== null) {
      window.clearInterval(tick.current);
      tick.current = null;
    }
  }

  function releaseRecorder() {
    const rec = recorder.current;
    recorder.current = null;
    if (rec && rec.state !== "inactive") {
      rec.onstop = null;
      try {
        rec.stop();
      } catch {
        stopTracks();
      }
    }
    stopTracks();
    chunks.current = [];
  }

  function showError(message: string) {
    focusAfter.current = "start";
    setError(message);
    onError?.(message);
    setHelp(IDLE_HELP);
    setLive(message);
  }

  function finish(blob: Blob, reachedCap: boolean) {
    setPhaseNow("transcribing");
    setHelp(reachedCap ? CAPPED_HELP : SENDING_HELP);
    setLive(reachedCap ? CAPPED_HELP : SENDING_HELP);
    void (async () => {
      try {
        const result = await transcribeAudio(blob);
        if (!alive.current) return;
        focusAfter.current = "line";
        onText(result.text);
        onError?.(null);
        setError(null);
        setHelp(REVIEW_HELP);
        setLive(REVIEW_HELP);
      } catch (err: unknown) {
        if (!alive.current) return;
        showError(failureMessage(err));
      } finally {
        if (alive.current) setPhaseNow("idle");
      }
    })();
  }

  function halt(next: Intent, status?: string) {
    if (phaseRef.current !== "recording") return;
    intent.current = next;
    clearClock();
    const note = status ?? (next === "discard" ? CANCELLED : "");
    if (next === "discard") focusAfter.current = "start";
    const rec = recorder.current;
    if (rec && rec.state !== "inactive") {
      rec.onstop = () => {
        const reachedCap = capped.current;
        const blob = new Blob(chunks.current, { type: rec.mimeType || "audio/webm" });
        chunks.current = [];
        stopTracks();
        recorder.current = null;
        if (!alive.current || intent.current === "discard") {
          if (alive.current) {
            setPhaseNow("idle");
            setElapsed(0);
            setError(null);
            onError?.(null);
            setHelp(IDLE_HELP);
            setLive(note);
          }
          return;
        }
        if (blob.size === 0) {
          if (alive.current) {
            setPhaseNow("idle");
            showError("Nothing was recorded. It was not sent. The line is unchanged.");
          }
          return;
        }
        if (blob.size > MAX_BYTES) {
          if (alive.current) {
            setPhaseNow("idle");
            showError("That recording is too long. It was not sent. The line is unchanged.");
          }
          return;
        }
        finish(blob, reachedCap);
      };
      rec.stop();
      return;
    }
    releaseRecorder();
    setPhaseNow("idle");
    setElapsed(0);
    setHelp(IDLE_HELP);
    setLive(note);
  }

  haltRef.current = halt;

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
    alive.current = true;
    return () => {
      alive.current = false;
      generation.current += 1;
      intent.current = "discard";
      if (timer.current !== null) window.clearTimeout(timer.current);
      if (tick.current !== null) window.clearInterval(tick.current);
      const rec = recorder.current;
      recorder.current = null;
      if (rec && rec.state !== "inactive") {
        rec.onstop = null;
        try {
          rec.stop();
        } catch {
          stream.current?.getTracks().forEach((track) => track.stop());
        }
      }
      stream.current?.getTracks().forEach((track) => track.stop());
      stream.current = null;
      chunks.current = [];
    };
  }, []);

  useEffect(() => {
    onBusy?.(phase === "opening" || phase === "recording" || phase === "transcribing");
  }, [onBusy, phase]);

  useEffect(() => {
    if (!disabled) return;
    generation.current += 1;
    if (phaseRef.current === "opening") {
      stopTracks();
      setPhaseNow("idle");
      return;
    }
    if (phaseRef.current === "recording") haltRef.current("discard", STOPPED);
  }, [disabled]);

  useEffect(() => {
    if (phase !== "recording") return;
    function onKey(event: KeyboardEvent) {
      if (event.key !== "Escape") return;
      event.preventDefault();
      haltRef.current("discard", CANCELLED);
    }
    function onHide() {
      if (document.visibilityState === "hidden") haltRef.current("discard", HIDDEN);
    }
    window.addEventListener("keydown", onKey);
    document.addEventListener("visibilitychange", onHide);
    return () => {
      window.removeEventListener("keydown", onKey);
      document.removeEventListener("visibilitychange", onHide);
    };
  }, [phase]);

  useEffect(() => {
    const before = previousPhase.current;
    previousPhase.current = phase;
    if (phase === "recording") stopButton.current?.focus();
    if (phase === "transcribing") statusNode.current?.focus();
    if (phase === "idle" && before !== "idle") {
      const target = focusAfter.current;
      focusAfter.current = null;
      if (target === "line") {
        const field = document.getElementById("feed-text");
        if (field instanceof HTMLInputElement) {
          field.focus();
          field.setSelectionRange(0, 0);
        }
      }
      else if (target === "start") startButton.current?.focus();
    }
  }, [phase]);

  if (!enabled) return null;

  async function start() {
    if (disabled || phaseRef.current !== "idle") return;
    const gen = generation.current + 1;
    generation.current = gen;
    setPhaseNow("opening");
    setError(null);
    onError?.(null);
    setLive("");
    capped.current = false;
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") {
      setPhaseNow("idle");
      showError("This browser has no microphone. Type the line instead. The line is unchanged.");
      return;
    }
    let media: MediaStream;
    try {
      media = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch (err: unknown) {
      if (!alive.current || gen !== generation.current) return;
      setPhaseNow("idle");
      showError(micMessage(err));
      return;
    }
    if (!alive.current || gen !== generation.current) {
      media.getTracks().forEach((track) => track.stop());
      return;
    }
    stream.current = media;
    chunks.current = [];
    let rec: MediaRecorder;
    try {
      rec = new MediaRecorder(media);
    } catch {
      stopTracks();
      setPhaseNow("idle");
      showError("This browser has no microphone. Type the line instead. The line is unchanged.");
      return;
    }
    recorder.current = rec;
    rec.ondataavailable = (event) => {
      if (event.data.size > 0) chunks.current.push(event.data);
    };
    try {
      rec.start();
    } catch {
      releaseRecorder();
      setPhaseNow("idle");
      showError("This browser has no microphone. Type the line instead. The line is unchanged.");
      return;
    }
    intent.current = "transcribe";
    elapsedMs.current = 0;
    setElapsed(0);
    setPhaseNow("recording");
    setHelp(RECORDING_HELP);
    setLive("Recording. Stop and transcribe sends this clip to Mistral. Cancel recording does not upload.");
    tick.current = window.setInterval(() => {
      elapsedMs.current = Math.min(MAX_MS, elapsedMs.current + TICK_MS);
      setElapsed(elapsedMs.current);
    }, TICK_MS);
    timer.current = window.setTimeout(() => {
      capped.current = true;
      elapsedMs.current = MAX_MS;
      setElapsed(MAX_MS);
      haltRef.current("transcribe");
    }, MAX_MS);
  }

  const recording = phase === "recording";
  const busy = phase === "opening" || phase === "transcribing";

  return (
    <div className={cx(inset, "flex flex-col gap-4")} data-voice="mic" data-voice-phase={phase} role="group" aria-labelledby="voice-title">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <p id="voice-title" className={kickerMuted}>
          Voice
        </p>
        {recording && (
          <p className="m-0 font-mono text-sm font-medium tabular-nums text-[var(--ink)]" data-voice-timer aria-hidden="true">
            {clock(elapsed)} / 0:30
          </p>
        )}
      </div>
      {recording && <p className="m-0 text-sm font-semibold text-[var(--ink)]">Recording</p>}
      {phase === "transcribing" && (
        <p ref={statusNode} className="m-0 text-sm font-semibold text-[var(--ink)]" tabIndex={-1}>
          Transcribing…
        </p>
      )}
      <p id="voice-help" className="m-0 text-sm leading-snug text-[var(--muted)]">
        {help}
      </p>
      <div className="flex flex-wrap items-center gap-2">
        {recording ? (
          <>
            <button
              ref={stopButton}
              type="button"
              className={cx(primary, "shrink-0")}
              onClick={() => {
                capped.current = false;
                halt("transcribe");
              }}
            >
              Stop and transcribe
            </button>
            <button
              type="button"
              className={cx(ghost, "shrink-0 text-[var(--danger)]")}
              onClick={() => halt("discard", CANCELLED)}
            >
              Cancel recording
            </button>
          </>
        ) : phase === "transcribing" ? null : (
          <button
            ref={startButton}
            type="button"
            className={cx(ghost, "shrink-0")}
            disabled={disabled || busy}
            aria-busy={phase === "opening" || undefined}
            onClick={() => void start()}
          >
            {phase === "opening" ? "Starting…" : "Start recording"}
          </button>
        )}
      </div>
      {error && (
        <p className={cx(errorText, "mb-0")} role="alert">
          {error}
        </p>
      )}
      <p className="sr-only" aria-live="polite">
        {live}
      </p>
    </div>
  );
}
