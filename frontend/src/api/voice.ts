import { ApiError } from "./client";

const base = import.meta.env.VITE_API_BASE_URL ?? "";

type ErrorPayload = { detail?: unknown } | null;

function messageFrom(payload: ErrorPayload, status: number): string {
  if (payload && typeof payload.detail === "string") return payload.detail;
  if (status === 0) return "The house log is not reachable.";
  return "The house log could not be reached.";
}

const FILE_EXT: Record<string, string> = {
  "audio/webm": "webm",
  "audio/mp4": "mp4",
  "audio/mpeg": "mp3",
  "audio/ogg": "ogg",
  "audio/wav": "wav",
  "audio/wave": "wav",
  "audio/x-m4a": "m4a",
  "video/webm": "webm",
};

/** The part name follows the recording's base type. A codecs parameter is not a filename. */
export function recordingName(audio: Blob): string {
  const base = (audio.type || "").split(";", 1)[0].trim().toLowerCase();
  return `line.${FILE_EXT[base] ?? "bin"}`;
}

/** One recording, in memory, exchanged for text. The browser does not keep the clip. */
export async function transcribeAudio(audio: Blob): Promise<{ text: string }> {
  const body = new FormData();
  body.append("file", audio, recordingName(audio));
  let response: Response;
  try {
    response = await fetch(`${base}/voice/transcribe`, {
      method: "POST",
      body,
      headers: { Accept: "application/json" },
    });
  } catch {
    throw new ApiError("The house log is not reachable.", 0);
  }
  const raw = await response.text();
  let payload: ErrorPayload = null;
  if (raw) {
    try {
      payload = JSON.parse(raw) as ErrorPayload;
    } catch {
      payload = null;
    }
  }
  if (!response.ok) throw new ApiError(messageFrom(payload, response.status), response.status);
  const text = payload && "text" in payload && typeof (payload as { text?: unknown }).text === "string" ? (payload as { text: string }).text : "";
  if (!text.trim()) throw new ApiError("Nothing was heard.", 422);
  return { text };
}
