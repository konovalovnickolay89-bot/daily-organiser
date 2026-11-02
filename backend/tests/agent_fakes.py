"""Test doubles for the Mistral assistant. Nothing here reaches the network."""

import json
from datetime import datetime
from zoneinfo import ZoneInfo

LONDON = ZoneInfo("Europe/London")


def london(year: int, month: int, day: int, hour: int = 0, minute: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=LONDON)


def call(name: str, arguments: dict | None = None, call_id: str | None = None) -> dict:
    """One function.call entry, as Mistral sends it."""
    return {
        "object": "entry",
        "type": "function.call",
        "tool_call_id": call_id or f"call_{name}",
        "name": name,
        "arguments": json.dumps(arguments or {}),
    }


def say(text: str) -> dict:
    """The assistant's closing message."""
    return {"object": "entry", "type": "message.output", "role": "assistant", "content": text}


class ScriptedMistral:
    """Stands in for Mistral. Each script step is one response's outputs, or an exception to raise."""

    def __init__(self, *script):
        self.script = list(script)
        self.calls: list[tuple] = []
        self.deleted: list[str] = []

    def start(self, agent_id, inputs):
        self.calls.append(("start", agent_id, inputs))
        return self._next()

    def append(self, conversation_id, inputs):
        self.calls.append(("append", conversation_id, inputs))
        return self._next()

    def delete(self, conversation_id):
        self.deleted.append(conversation_id)

    def close(self):
        pass

    def results(self) -> list[dict]:
        """Every function result the house sent back, decoded."""
        return [
            json.loads(entry["result"])
            for kind, _, inputs in self.calls
            if kind == "append"
            for entry in inputs
        ]

    def _next(self):
        if not self.script:
            raise AssertionError("Mistral was called more times than the test scripted.")
        step = self.script.pop(0)
        if isinstance(step, Exception):
            raise step
        return {"object": "conversation.response", "conversation_id": "conv_test", "outputs": step, "usage": {}}
