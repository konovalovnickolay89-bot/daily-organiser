"""One run of the assistant: start, answer its function calls, keep the reply.

The caller adds the run row, commits proposals only when the run finishes, and
rolls everything back if it fails, so a failed run leaves nothing pending.
"""

import json
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from organiser.agent.functions import RunContext, dispatch
from organiser.agent.mistral import (
    MistralUnavailable,
    function_calls,
    function_result,
    message_text,
    used_web_search,
)
from organiser.agent.rules import Candidate

logger = logging.getLogger(__name__)

MAX_ROUNDS = 6
RUN_DEADLINE_SECONDS = 120.0
REPLY_LINES = 2
REPLY_CHARS = 240


class Conversations(Protocol):
    def start(self, agent_id: str, inputs: str | list[dict]) -> dict: ...

    def append(self, conversation_id: str, inputs: list[dict]) -> dict: ...

    def delete(self, conversation_id: str) -> None: ...


class RunFailed(Exception):
    """The run stopped before a reply. Nothing it proposed is kept."""


@dataclass
class RunResult:
    reply: str | None
    searched: bool
    rounds: int


def clean_reply(text: str | None) -> str | None:
    """At most two short lines. The screen shows this as a log line, not a chat bubble."""
    if not text:
        return None
    lines = [" ".join(line.split()) for line in text.splitlines()]
    lines = [line for line in lines if line][:REPLY_LINES]
    if not lines:
        return None
    reply = "\n".join(lines)
    return reply if len(reply) <= REPLY_CHARS else reply[: REPLY_CHARS - 1].rstrip() + "…"


def run_agent(
    client: Conversations,
    agent_id: str,
    ctx: RunContext,
    packet: str,
    *,
    deadline_seconds: float = RUN_DEADLINE_SECONDS,
    monotonic: Callable[[], float] = time.monotonic,
) -> RunResult:
    started = monotonic()
    conversation_id: str | None = None
    try:
        response = client.start(agent_id, packet)
        conversation_id = response.get("conversation_id") or None
        searched = used_web_search(response)
        rounds = 0
        while True:
            calls = function_calls(response)
            if not calls:
                break
            if rounds >= MAX_ROUNDS:
                raise RunFailed("The assistant did not finish.")
            if monotonic() - started > deadline_seconds:
                raise RunFailed("The assistant took too long.")
            if not conversation_id:
                raise RunFailed("Mistral did not return a conversation.")
            results = [
                function_result(
                    str(call.get("tool_call_id", "")),
                    json.dumps(dispatch(ctx, str(call.get("name", "")), call.get("arguments")), default=str),
                )
                for call in calls
            ]
            response = client.append(conversation_id, results)
            searched = searched or used_web_search(response)
            rounds += 1
        return RunResult(reply=clean_reply(message_text(response)), searched=searched, rounds=rounds)
    finally:
        if conversation_id:
            try:
                client.delete(conversation_id)
            except MistralUnavailable:
                logger.warning("Could not delete Mistral conversation %s.", conversation_id)


# --- run briefs ------------------------------------------------------------


def _header(trigger: str, local_now: datetime, tz_name: str, limit: int) -> list[str]:
    when = f"{local_now.strftime('%A')} {local_now.day} {local_now.strftime('%B %Y, %H:%M')}"
    return [f"Trigger: {trigger}", f"House time: {when} ({tz_name})", f"Proposal limit: {limit}"]


def feed_packet(local_now: datetime, tz_name: str, limit: int, text: str) -> str:
    lines = _header("feed", local_now, tz_name, limit)
    lines += ["Nick wrote:", '"""', text.strip(), '"""']
    return "\n".join(lines)


def morning_packet(local_now: datetime, tz_name: str, limit: int, brief: dict) -> str:
    lines = _header("morning_review", local_now, tz_name, limit)
    lines.append("Today's brief:")
    for section in brief["sections"]:
        if section["key"] not in ("tasks", "commitments"):
            continue
        kind = "task" if section["key"] == "tasks" else "commitment"
        lines.append(f"{section['title']}: {section['summary']}")
        for item in section["items"]:
            lines.append(f"- {kind} {item['id']}: {item['title']} ({item['meta']})")
    return "\n".join(lines)


def stale_packet(local_now: datetime, tz_name: str, limit: int, candidate: Candidate) -> str:
    lines = _header(candidate.rule, local_now, tz_name, limit)
    changed = candidate.ref_updated_at.astimezone(local_now.tzinfo)
    lines += [
        f"Item: {candidate.ref_type} {candidate.ref_id}",
        f"Title: {candidate.title}",
        f"Status: {candidate.status}",
        f"Due: {candidate.due_on.isoformat() if candidate.due_on else 'no date'}",
        f"Last change: {changed.strftime('%a')} {changed.day} {changed.strftime('%b %H:%M')}",
        f"Why now: {candidate.reason}",
        "Propose exactly one fix for this item, or nothing if no fix helps.",
    ]
    return "\n".join(lines)
