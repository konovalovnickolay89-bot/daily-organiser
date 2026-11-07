"""A thin client for Mistral's Agents and Conversations REST API.

Five calls, checked against the paths in mistralai/client-python:

    start          POST   /v1/conversations
    append         POST   /v1/conversations/{conversation_id}
    delete         DELETE /v1/conversations/{conversation_id}
    create_agent   POST   /v1/agents
    update_agent   PATCH  /v1/agents/{agent_id}

No SDK: it changed its imports twice in 2026, and this app needs only these.
Errors raise ``MistralUnavailable`` with a short message that never holds the key.
"""

import re
from typing import Any

import httpx

from organiser.jsonlog import COORD_PATTERN, POSTCODE_PATTERN
from organiser.metrics import observe_mistral

DEFAULT_BASE_URL = "https://api.mistral.ai"


class MistralUnavailable(Exception):
    """Mistral could not be reached, or refused the call.

    ``category`` is timeout, network, http, unreadable, or empty.
    ``upstream_status`` is the HTTP status when Mistral sent one.
    The message never includes the response body, the audio, or the key.
    """

    def __init__(self, message: str, *, category: str = "unknown", upstream_status: int | None = None) -> None:
        super().__init__(message)
        self.category = category
        self.upstream_status = upstream_status


class MistralClient:
    def __init__(
        self,
        api_key: str,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = 25.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._http = httpx.Client(
            base_url=base_url.rstrip("/"),
            timeout=timeout,
            transport=transport,
            headers={"Authorization": f"Bearer {api_key}", "Accept": "application/json"},
        )

    def close(self) -> None:
        self._http.close()

    def _call(self, method: str, path: str, body: dict | None = None) -> dict:
        try:
            response = self._http.request(method, path, json=body)
        except httpx.TimeoutException:
            raise MistralUnavailable("Mistral did not answer in time.") from None
        except httpx.HTTPError:
            raise MistralUnavailable("Mistral could not be reached.") from None
        if response.status_code >= 400:
            raise MistralUnavailable(f"Mistral refused the call ({response.status_code}{_detail(response)}).")
        if response.status_code == 204 or not response.content:
            return {}
        try:
            return response.json()
        except ValueError:
            raise MistralUnavailable("Mistral sent something that is not JSON.") from None

    def start(self, agent_id: str, inputs: str | list[dict]) -> dict:
        # store=true: the run appends function results to this conversation.
        # The runner deletes the conversation when the run ends.
        return self._call("POST", "/v1/conversations", {"agent_id": agent_id, "inputs": inputs, "store": True})

    def append(self, conversation_id: str, inputs: list[dict]) -> dict:
        return self._call("POST", f"/v1/conversations/{conversation_id}", {"inputs": inputs, "store": True})

    def delete(self, conversation_id: str) -> None:
        self._call("DELETE", f"/v1/conversations/{conversation_id}")

    def create_agent(self, body: dict) -> dict:
        return self._call("POST", "/v1/agents", body)

    def update_agent(self, agent_id: str, body: dict) -> dict:
        return self._call("PATCH", f"/v1/agents/{agent_id}", body)

    def embed(self, text: str, *, model: str = "mistral-embed") -> list[float]:
        """One embedding. Refuses a postcode or a coordinate before the request is built."""
        if POSTCODE_PATTERN.search(text) or COORD_PATTERN.search(text):
            raise MistralUnavailable("Refused to send a location.")
        if re.search(r"\b(lat(?:itude)?|lon(?:gitude)?|postcode)\s*[:=]", text, re.IGNORECASE):
            raise MistralUnavailable("Refused to send a location.")
        body = observe_mistral(lambda: self._call("POST", "/v1/embeddings", {"model": model, "input": [text]}))
        data = body.get("data")
        if not isinstance(data, list) or not data or not isinstance(data[0], dict):
            raise MistralUnavailable("Mistral sent no embedding.")
        vector = data[0].get("embedding")
        if not isinstance(vector, list) or not vector or not all(isinstance(item, (int, float)) for item in vector):
            raise MistralUnavailable("Mistral sent no embedding.")
        return [float(item) for item in vector]

    def complete(
        self,
        *,
        model: str,
        messages: list[dict],
        max_tokens: int = 80,
        response_format: dict | None = None,
    ) -> str:
        """One short completion. No tools. Catch-up wording and reminder assessment use it."""
        payload: dict = {"model": model, "temperature": 0.2, "max_tokens": max_tokens, "messages": messages}
        if response_format is not None:
            payload["response_format"] = response_format
        body = observe_mistral(lambda: self._call("POST", "/v1/chat/completions", payload))
        choices = body.get("choices")
        if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
            raise MistralUnavailable("Mistral sent no note.")
        message = choices[0].get("message")
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, str) or not content.strip():
            raise MistralUnavailable("Mistral sent no note.")
        return content.strip()

    def transcribe(self, audio: bytes, *, model: str, media_type: str) -> str:
        """One transcription. The audio bytes stay on this request and are not logged.

        The part name has an extension that matches the base media type. A codecs
        parameter is not forwarded. The model id is the caller's.
        """
        if not audio:
            raise MistralUnavailable("There was no audio.", category="empty")
        name, base = upload_part(media_type)
        try:
            response = self._http.post(
                "/v1/audio/transcriptions",
                data={"model": model},
                files={"file": (name, audio, base)},
            )
        except httpx.TimeoutException:
            raise MistralUnavailable("Mistral did not answer in time.", category="timeout") from None
        except httpx.HTTPError:
            raise MistralUnavailable("Mistral could not be reached.", category="network") from None
        if response.status_code >= 400:
            raise MistralUnavailable(
                "Mistral refused the transcription.",
                category="http",
                upstream_status=response.status_code,
            ) from None
        try:
            body = response.json()
        except ValueError:
            raise MistralUnavailable("Mistral sent something that is not JSON.", category="unreadable") from None
        text = body.get("text") if isinstance(body, dict) else None
        if not isinstance(text, str) or not text.strip():
            raise MistralUnavailable("Mistral sent no text.", category="empty")
        return text.strip()


_UPLOAD_EXT = {
    "audio/webm": "webm",
    "audio/ogg": "ogg",
    "audio/wav": "wav",
    "audio/wave": "wav",
    "audio/mpeg": "mp3",
    "audio/mp4": "mp4",
    "audio/x-m4a": "m4a",
    "video/webm": "webm",
}


def upload_part(media_type: str) -> tuple[str, str]:
    """Filename and base type for one transcription part. No codecs parameter."""
    base = (media_type or "").split(";", 1)[0].strip().lower() or "application/octet-stream"
    return f"line.{_UPLOAD_EXT.get(base, 'bin')}", base


def _detail(response: httpx.Response) -> str:
    """A short reason from Mistral's error body, such as an unknown model name."""
    try:
        payload = response.json()
    except ValueError:
        return ""
    message: Any = (payload.get("message") or payload.get("detail")) if isinstance(payload, dict) else None
    if isinstance(message, list):
        message = "; ".join(str(item.get("msg", item)) if isinstance(item, dict) else str(item) for item in message)
    if not message:
        return ""
    return f": {str(message)[:160]}"


def function_result(tool_call_id: str, result: str) -> dict:
    return {"object": "entry", "type": "function.result", "tool_call_id": tool_call_id, "result": result}


def outputs(response: dict) -> list[dict]:
    items = response.get("outputs")
    return [item for item in items if isinstance(item, dict)] if isinstance(items, list) else []


def function_calls(response: dict) -> list[dict]:
    return [item for item in outputs(response) if item.get("type") == "function.call"]


def used_web_search(response: dict) -> bool:
    return any(
        item.get("type") == "tool.execution" and "web_search" in str(item.get("name", ""))
        for item in outputs(response)
    )


def message_text(response: dict) -> str | None:
    """Text of the last assistant message. Thinking chunks are dropped, never shown or stored."""
    messages = [item for item in outputs(response) if item.get("type") == "message.output"]
    if not messages:
        return None
    content = messages[-1].get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = [
            chunk.get("text", "")
            for chunk in content
            if isinstance(chunk, dict) and chunk.get("type") == "text" and isinstance(chunk.get("text"), str)
        ]
        return "".join(parts)
    return None
