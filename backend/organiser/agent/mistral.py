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

from typing import Any

import httpx

DEFAULT_BASE_URL = "https://api.mistral.ai"


class MistralUnavailable(Exception):
    """Mistral could not be reached, or refused the call."""


class MistralClient:
    def __init__(
        self,
        api_key: str,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = 60.0,
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
