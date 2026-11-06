"""The HTTP calls to Mistral, against a mock transport. Nothing leaves the test."""

import json

import httpx
import pytest

from organiser.agent.mistral import (
    MistralClient,
    MistralUnavailable,
    function_calls,
    function_result,
    message_text,
    used_web_search,
)
from organiser.agent.spec import agent_definition
from organiser.config import Settings

KEY = "sk-test-not-a-real-key"


def _client(handler) -> MistralClient:
    return MistralClient(KEY, "https://api.mistral.test", 5, transport=httpx.MockTransport(handler))


def test_conversation_calls_use_the_documented_paths_and_bodies():
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content) if request.content else None
        seen.append((request.method, request.url.path, request.headers["authorization"], body))
        if request.method == "DELETE":
            return httpx.Response(204)
        return httpx.Response(200, json={"conversation_id": "conv_1", "outputs": []})

    client = _client(handler)
    client.start("ag_1", "Trigger: feed")
    client.append("conv_1", [function_result("call_1", '{"ok": true}')])
    client.delete("conv_1")

    assert seen[0] == (
        "POST",
        "/v1/conversations",
        f"Bearer {KEY}",
        {"agent_id": "ag_1", "inputs": "Trigger: feed", "store": True},
    )
    assert seen[1] == (
        "POST",
        "/v1/conversations/conv_1",
        f"Bearer {KEY}",
        {
            "inputs": [
                {"object": "entry", "type": "function.result", "tool_call_id": "call_1", "result": '{"ok": true}'}
            ],
            "store": True,
        },
    )
    assert seen[2][:2] == ("DELETE", "/v1/conversations/conv_1")


def test_agent_calls_create_then_update():
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append((request.method, request.url.path, json.loads(request.content)))
        return httpx.Response(200, json={"id": "ag_new", "version": 2})

    body = agent_definition(Settings())
    client = _client(handler)
    assert client.create_agent(body)["id"] == "ag_new"
    client.update_agent("ag_new", body)
    assert [(method, path) for method, path, _ in seen] == [("POST", "/v1/agents"), ("PATCH", "/v1/agents/ag_new")]
    assert seen[0][2]["tools"][0] == {"type": "web_search"}
    assert seen[0][2]["completion_args"]["reasoning_effort"] == "high"


@pytest.mark.parametrize(
    ("handler", "phrase"),
    [
        (lambda request: httpx.Response(401, json={"message": "Unauthorized"}), "refused the call (401: Unauthorized)"),
        (lambda request: httpx.Response(500, text="oops"), "refused the call (500)"),
        (lambda request: (_ for _ in ()).throw(httpx.ConnectError("no route")), "could not be reached"),
        (lambda request: (_ for _ in ()).throw(httpx.ReadTimeout("slow")), "did not answer in time"),
    ],
)
def test_errors_are_short_and_never_hold_the_key(handler, phrase):
    with pytest.raises(MistralUnavailable) as raised:
        _client(handler).start("ag_1", "hello")
    assert phrase in str(raised.value)
    assert KEY not in str(raised.value)
    assert raised.value.__cause__ is None


def test_reply_text_drops_thinking_and_keeps_text():
    response = {
        "outputs": [
            {"type": "tool.execution", "name": "web_search"},
            {
                "type": "message.output",
                "content": [
                    {"type": "thinking", "thinking": [{"type": "text", "text": "private reasoning"}]},
                    {"type": "text", "text": "Added 1 proposal: "},
                    {"type": "tool_reference", "tool": "web_search", "title": "Council", "url": "https://x"},
                    {"type": "text", "text": "bins (Fri)."},
                ],
            },
        ]
    }
    assert message_text(response) == "Added 1 proposal: bins (Fri)."
    assert used_web_search(response) is True
    assert function_calls(response) == []


def test_complete_reads_the_chat_message_and_hides_the_key():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"choices": [{"message": {"content": "  Bins are due today.  "}}]})

    client = _client(handler)
    assert client.complete(model="mistral-small-latest", messages=[{"role": "user", "content": "Bins"}]) == (
        "Bins are due today."
    )
    assert seen["path"] == "/v1/chat/completions"
    assert seen["body"]["model"] == "mistral-small-latest"
    assert KEY not in json.dumps(seen["body"])


def test_plain_string_reply_and_no_reply():
    assert message_text({"outputs": [{"type": "message.output", "content": "Paused."}]}) == "Paused."
    assert message_text({"outputs": []}) is None
    assert message_text({}) is None
    assert used_web_search({"outputs": [{"type": "message.output", "content": "x"}]}) is False
