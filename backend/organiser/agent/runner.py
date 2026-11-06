"""One run of the assistant: start, answer its function calls, keep the reply.

The caller adds the run row, commits proposals only when the run finishes, and
rolls everything back if it fails, so a failed run leaves nothing pending.
"""

import json
import logging
import re
import time
from collections.abc import Callable, Iterator
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
from organiser.metrics import observe_mistral

logger = logging.getLogger(__name__)

# A feed has to finish inside Cloudflare's ~100s proxy limit. The deadline is
# checked before each further call, and one call may already be in flight, so
# the worst case is the deadline plus one Mistral timeout (25s): under 100s.
# Five tool rounds cover a read, a search, two proposals, and one correction.
MAX_ROUNDS = 5
RUN_DEADLINE_SECONDS = 68.0
REPLY_LINES = 2
REPLY_CHARS = 240
READ_FUNCTIONS = frozenset({"get_state", "search_items", "get_item"})

# Household travel only. Hilton, a guest, a colleague, an employer, or a work
# system stays out. A personal hotel booking does not.
_JOURNEY_RE = re.compile(
    r"\b("
    r"commutes?|commuting"
    r"|journeys?"
    r"|travell?ing to work"
    r"|travel to work"
    r"|get(?:ting)? to work"
    r"|trains? to work"
    r"|bus(?:es)? to work"
    r")\b",
    re.IGNORECASE,
)
_OUTSIDE_HOME_RE = re.compile(
    r"\b("
    r"hilton"
    r"|guests?"
    r"|colleagues?"
    r"|employers?"
    r"|coworkers?|co-workers?|workmates?"
    r"|workplace"
    r"|payroll"
    r"|work\s+emails?"
    r"|work\s+phones?"
    r"|at\s+work"
    r")\b",
    re.IGNORECASE,
)
JOURNEY_NOTE = (
    "Journey: this is travel to work. Propose the trip if it is not already a task. "
    "The morning brief reads the rota and TfL for a commute to Wembley Park. "
    "Do not invent disruptions or a live lookup on the card."
)


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


def iter_run(
    client: Conversations,
    agent_id: str,
    ctx: RunContext,
    packet: str,
    *,
    deadline_seconds: float = RUN_DEADLINE_SECONDS,
    monotonic: Callable[[], float] = time.monotonic,
) -> Iterator[str | RunResult]:
    """Yield a step id as the run moves, then one ``RunResult``.

    Step ids are ``calling`` (a Mistral request is about to start) and
    ``reading`` (a read of the house log is about to run). The caller turns
    those into the lines on the screen.
    """
    started = monotonic()
    conversation_id: str | None = None
    try:
        yield "calling"
        response = observe_mistral(lambda: client.start(agent_id, packet))
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
            if any(str(call.get("name", "")) in READ_FUNCTIONS for call in calls):
                yield "reading"
            results = [
                function_result(
                    str(call.get("tool_call_id", "")),
                    json.dumps(dispatch(ctx, str(call.get("name", "")), call.get("arguments")), default=str),
                )
                for call in calls
            ]
            yield "calling"
            response = observe_mistral(lambda: client.append(conversation_id, results))
            searched = searched or used_web_search(response)
            rounds += 1
        yield RunResult(reply=clean_reply(message_text(response)), searched=searched, rounds=rounds)
    finally:
        if conversation_id:
            try:
                client.delete(conversation_id)
            except MistralUnavailable:
                logger.warning("Could not delete Mistral conversation %s.", conversation_id)


def run_agent(
    client: Conversations,
    agent_id: str,
    ctx: RunContext,
    packet: str,
    *,
    deadline_seconds: float = RUN_DEADLINE_SECONDS,
    monotonic: Callable[[], float] = time.monotonic,
    on_step: Callable[[str], None] | None = None,
) -> RunResult:
    result: RunResult | None = None
    for item in iter_run(
        client,
        agent_id,
        ctx,
        packet,
        deadline_seconds=deadline_seconds,
        monotonic=monotonic,
    ):
        if isinstance(item, str):
            if on_step is not None:
                on_step(item)
            continue
        result = item
    if result is None:
        raise RunFailed("The assistant did not finish.")
    return result


# --- run briefs ------------------------------------------------------------


def _header(trigger: str, local_now: datetime, tz_name: str, limit: int) -> list[str]:
    when = f"{local_now.strftime('%A')} {local_now.day} {local_now.strftime('%B %Y, %H:%M')}"
    return [f"Trigger: {trigger}", f"House time: {when} ({tz_name})", f"Proposal limit: {limit}"]


def outside_home(text: str) -> bool:
    """Hilton, a guest, a colleague, an employer, or work is not house business.

    A personal hotel booking, such as a stay in Lisbon, is household life.
    """
    return _OUTSIDE_HOME_RE.search(text) is not None


def journey_note(text: str) -> str | None:
    """A commute asks for the trip and a journey check. Anything outside the house does not."""
    if outside_home(text) or not _JOURNEY_RE.search(text):
        return None
    return JOURNEY_NOTE


def _with_context(packet: str, context: object | None) -> str:
    if context is None:
        return packet
    rendered = context.model_dump_json() if hasattr(context, "model_dump_json") else str(context)
    return packet + "\n\nContext:\n" + rendered


def feed_packet(local_now: datetime, tz_name: str, limit: int, text: str, context: object | None = None) -> str:
    """The Smart Add packet. A context, when passed, is appended and does not rewrite the head."""
    lines = _header("feed", local_now, tz_name, limit)
    lines += ["Nick wrote:", '"""', text.strip(), '"""']
    note = journey_note(text)
    if note:
        lines.append(note)
    return _with_context("\n".join(lines), context)


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


def stale_packet(
    local_now: datetime,
    tz_name: str,
    limit: int,
    candidate: Candidate,
    context: object | None = None,
) -> str:
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
    return _with_context("\n".join(lines), context)
