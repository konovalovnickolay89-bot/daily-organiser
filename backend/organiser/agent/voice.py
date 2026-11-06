"""Voice on Smart Add. Audio stays in memory and comes back as text.

The flag ``VOICE_INPUT_ENABLED`` is off unless the house turns it on.
A transcript is a task, a shopping item, or remember / forget. Anything else
is refused. Nothing is written here: no file, no row, no log of the words.
"""

import re
from typing import Literal, Protocol

from organiser.agent.memory import outside_memory, parse_memory_intent
from organiser.agent.mistral import MistralClient, MistralUnavailable
from organiser.agent.runner import outside_home
from organiser.metrics import observe_mistral

MAX_SECONDS = 30
# Speech for that half minute fits well under this. The request is refused
# before a larger body is kept, and the bytes are never given a path.
MAX_BYTES = 512 * 1024
MAX_BODY = MAX_BYTES + 8192

Kind = Literal["task", "shopping", "remember", "forget"]

_SHOPPING = re.compile(
    r"^\s*(?:please\s+)?(?:buy|get|pick up|shop(?:ping)?(?:\s+for)?)\b"
    r"|^\s*(?:please\s+)?add\b.+\b(?:list|shopping)\b"
    r"|\bshopping list\b",
    re.IGNORECASE,
)
# A question, a commitment, an approval, or a message is not a voice line.
_NOT_VOICE = re.compile(
    r"\b(?:commitments?|appointments?|meetings?|meet|approvals?|approve|emails?|e-mails?)\b"
    r"|\?\s*$",
    re.IGNORECASE,
)
_ALLOWED_MEDIA = frozenset(
    {
        "audio/webm",
        "audio/ogg",
        "audio/wav",
        "audio/wave",
        "audio/mpeg",
        "audio/mp4",
        "audio/x-m4a",
        "video/webm",
        "application/octet-stream",
    }
)


class Transcriber(Protocol):
    def transcribe(self, audio: bytes, media_type: str) -> str: ...


class VoiceRefused(Exception):
    def __init__(self, detail: str, status_code: int) -> None:
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


def media_base(value: str) -> str:
    return (value or "").split(";", 1)[0].strip().lower()


def voice_kind(text: str) -> Kind | None:
    """Tasks, shopping items, and remember / forget. House text only."""
    cleaned = " ".join((text or "").split())
    if not cleaned or outside_home(cleaned):
        return None
    intent = parse_memory_intent(cleaned)
    if intent is not None:
        if outside_memory(intent.text):
            return None
        return intent.action
    if _NOT_VOICE.search(cleaned):
        return None
    if _SHOPPING.search(cleaned):
        return "shopping"
    return "task"


def accept_transcript(text: str) -> str:
    """The line for the box, or a refusal. The refusal does not echo the words."""
    cleaned = " ".join((text or "").split())
    if not cleaned:
        raise VoiceRefused("Nothing was heard.", 422)
    if len(cleaned) > 1000:
        raise VoiceRefused("Keep a voice line short.", 422)
    if outside_home(cleaned):
        raise VoiceRefused("Not for the house log.", 422)
    intent = parse_memory_intent(cleaned)
    if intent is not None and outside_memory(intent.text):
        raise VoiceRefused("Not for the house log.", 422)
    if voice_kind(cleaned) is None:
        raise VoiceRefused("Voice is for a task, a shop item, or remember and forget.", 422)
    return cleaned


def audio_part(body: bytes, content_type: str) -> tuple[bytes, str]:
    """The file field of one multipart body. Parsed in memory."""
    if "multipart/form-data" not in (content_type or "").lower():
        raise VoiceRefused("Send the recording as a file.", 422)
    marker = ""
    for piece in content_type.split(";"):
        piece = piece.strip()
        if piece.lower().startswith("boundary="):
            marker = piece.split("=", 1)[1].strip().strip('"')
    if not marker:
        raise VoiceRefused("Send the recording as a file.", 422)
    delimiter = b"--" + marker.encode()
    for chunk in body.split(delimiter):
        if not chunk or chunk.startswith(b"--"):
            continue
        head, sep, data = chunk.partition(b"\r\n\r\n")
        if not sep:
            head, sep, data = chunk.partition(b"\n\n")
        if not sep or b"name=" not in head.lower():
            continue
        header = head.decode("latin-1", "replace")
        if not re.search(r'name="file"|name=file\b', header, re.IGNORECASE):
            continue
        if data.endswith(b"\r\n"):
            data = data[:-2]
        elif data.endswith(b"\n"):
            data = data[:-1]
        media = "application/octet-stream"
        for line in header.splitlines():
            if line.lower().startswith("content-type:"):
                media = line.split(":", 1)[1].strip() or media
        return data, media
    raise VoiceRefused("Send the recording as a file.", 422)


def take_audio(body: bytes, content_type: str) -> tuple[bytes, str]:
    if len(body) > MAX_BODY:
        raise VoiceRefused("That recording is too long.", 413)
    audio, media = audio_part(body, content_type)
    if not audio:
        raise VoiceRefused("Nothing was recorded.", 422)
    if len(audio) > MAX_BYTES:
        raise VoiceRefused("That recording is too long.", 413)
    if media_base(media) not in _ALLOWED_MEDIA:
        raise VoiceRefused("That recording is not audio.", 422)
    return audio, media


class VoxtralTranscriber:
    """Mistral Voxtral. The audio is a memory buffer on the request, then dropped."""

    def __init__(self, api_key: str, base_url: str, model: str, timeout: float) -> None:
        self._client = MistralClient(api_key, base_url, timeout)
        self._model = model

    def transcribe(self, audio: bytes, media_type: str) -> str:
        try:
            return self._client.transcribe(audio, model=self._model, media_type=media_type)
        finally:
            self._client.close()


def transcribe_with(transcriber: Transcriber, audio: bytes, media_type: str) -> str:
    if not isinstance(audio, bytes):
        raise VoiceRefused("Nothing was recorded.", 422)
    try:
        text = observe_mistral(lambda: transcriber.transcribe(audio, media_type))
    except MistralUnavailable:
        raise VoiceRefused("Voice could not be transcribed. Nothing was saved.", 503) from None
    if not isinstance(text, str):
        raise VoiceRefused("Voice could not be transcribed. Nothing was saved.", 503)
    return accept_transcript(text)
