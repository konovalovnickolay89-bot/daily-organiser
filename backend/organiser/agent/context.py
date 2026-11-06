"""The context a Mistral read can take. Schema version 1.

Smart Add sees three days of the house log. Catch-up and follow-ups see seven.
Memory is at most ten lines, chosen for the query by similarity and recency.
The home-scope filter runs once, while the context is built, and is not applied
again when the packet is rendered. Sections over the token budget are shortened
in a fixed order: log, waiting, commitments, tasks, then memory. Within a
section the tail goes first, which is the oldest log line, the oldest waiting
card, the last title, or the weakest memory. A follow-up's focus line is kept.

The log line for a build is the counts. It does not include a title or a memory.
The only write is ``last_used_at`` on the memories that stayed in the context.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from organiser.agent.memory import redact_for_model, retrieve_memories
from organiser.agent.runner import outside_home
from organiser.config import get_settings
from organiser.models import AgentProposal, Commitment, Event, MemoryItem, Task
from organiser.services.settings import context_limits

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 1
# Four characters of the context JSON stand in for one token.
CHARS_PER_TOKEN = 4
TOKEN_BUDGET = 2000
# Lowest priority first. Focus is not in this list, so a follow-up keeps it.
TRIM_ORDER = ("log", "waiting", "commitments", "tasks", "memory")
MEMORY_LIMIT = 10
LOG_DAYS = {"smart_add": 3, "catch_up": 7, "follow_up": 7}
Purpose = Literal["smart_add", "catch_up", "follow_up"]


class ContextEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["task", "commitment", "waiting", "log"]
    id: str
    title: str
    status: str | None = None
    due_on: str | None = None
    at: str | None = None


class MemoryContextItem(BaseModel):
    """One memory in the slot. No embedding, postcode, or coordinate."""

    model_config = ConfigDict(extra="forbid")

    id: str
    kind: Literal["preference", "fact", "routine"]
    text: str
    pinned: bool


class MemorySlot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    limit: int
    items: list[MemoryContextItem]


class HouseContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: int = SCHEMA_VERSION
    purpose: Purpose
    time: str
    theme: Literal["morning", "evening"]
    tasks: list[ContextEntry]
    commitments: list[ContextEntry]
    waiting: list[ContextEntry]
    log: list[ContextEntry]
    log_days: int
    memory: MemorySlot
    focus: ContextEntry | None = None
    trimmed: bool = False


@dataclass(frozen=True)
class _Draft:
    entry: ContextEntry
    extra: str = ""


def theme_for_time(local: datetime) -> Literal["morning", "evening"]:
    """Same split as the arrival screen: 05:00–16:59 morning, otherwise evening."""
    return "morning" if 5 <= local.hour < 17 else "evening"


def token_count(context: HouseContext) -> int:
    raw = len(context.model_dump_json())
    return max(1, (raw + CHARS_PER_TOKEN - 1) // CHARS_PER_TOKEN)


def apply_home_scope(
    sections: dict[str, list[_Draft]],
    focus: _Draft | None,
) -> tuple[dict[str, list[ContextEntry]], ContextEntry | None]:
    """One pass. A hotel brand, a guest, a colleague, an employer, or work is left out.

    A personal hotel booking stays. Callers do not filter these sections again.
    """
    kept: dict[str, list[ContextEntry]] = {}
    for name, drafts in sections.items():
        section: list[ContextEntry] = []
        for draft in drafts:
            blob = " ".join(part for part in (draft.entry.title, draft.extra) if part)
            if blob and outside_home(blob):
                continue
            section.append(draft.entry)
        kept[name] = section
    kept_focus = None
    if focus is not None:
        blob = " ".join(part for part in (focus.entry.title, focus.extra) if part)
        if not blob or not outside_home(blob):
            kept_focus = focus.entry
    return kept, kept_focus


def trim_to_budget(context: HouseContext, budget: int | None = None) -> HouseContext:
    """Drop the tail of the lowest-priority section until the budget holds."""
    limit = TOKEN_BUDGET if budget is None else budget
    while token_count(context) > limit:
        if not _drop_one(context):
            break
        context.trimmed = True
    return context


def _drop_one(context: HouseContext) -> bool:
    for name in TRIM_ORDER:
        if name == "memory":
            if context.memory.items:
                context.memory.items.pop()
                return True
            continue
        items: list[ContextEntry] = getattr(context, name)
        if items:
            items.pop()
            return True
    return False


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=ZoneInfo("UTC"))
    return value.isoformat(timespec="seconds")


def _log_counts(context: HouseContext) -> None:
    """Counts only. A title, a memory, or the query must not be interpolated here."""
    logger.info(
        "context schema=%s purpose=%s tasks=%s commitments=%s waiting=%s log=%s memory=%s tokens=%s trimmed=%s",
        context.schema_version,
        context.purpose,
        len(context.tasks),
        len(context.commitments),
        len(context.waiting),
        len(context.log),
        len(context.memory.items),
        token_count(context),
        int(context.trimmed),
    )


def build_context(
    session: Session,
    *,
    purpose: Purpose,
    now: datetime,
    query: str | None = None,
    focus: ContextEntry | None = None,
) -> HouseContext:
    """Assemble one context. The home-scope pass runs once, then the budget."""
    settings = get_settings()
    limits = context_limits(session)
    local = now.astimezone(ZoneInfo(settings.house_timezone))
    log_days = limits.smart_add_days if purpose == "smart_add" else limits.catch_up_days
    since = local - timedelta(days=log_days)

    tasks: list[_Draft] = []
    for row in session.scalars(select(Task).where(Task.status != "done").order_by(Task.title.asc())):
        tasks.append(
            _Draft(
                ContextEntry(
                    kind="task",
                    id=str(row.id),
                    title=row.title,
                    status=row.status,
                    due_on=row.due_on.isoformat() if row.due_on else None,
                ),
                extra=row.detail or "",
            )
        )

    commitments: list[_Draft] = []
    for row in session.scalars(
        select(Commitment).where(Commitment.status == "open").order_by(Commitment.title.asc())
    ):
        commitments.append(
            _Draft(
                ContextEntry(
                    kind="commitment",
                    id=str(row.id),
                    title=row.title,
                    status=row.status,
                    due_on=row.due_on.isoformat() if row.due_on else None,
                ),
                extra=row.detail or "",
            )
        )

    waiting: list[_Draft] = []
    pending = session.scalars(
        select(AgentProposal).where(AgentProposal.status == "pending").order_by(AgentProposal.created_at.desc())
    )
    for row in pending:
        waiting.append(
            _Draft(
                ContextEntry(
                    kind="waiting",
                    id=str(row.id),
                    title=row.summary,
                    status=row.status,
                    at=_iso(row.created_at),
                ),
                extra=row.reason or "",
            )
        )

    log: list[_Draft] = []
    events = session.scalars(
        select(Event).where(Event.recorded_at >= since).order_by(Event.recorded_at.desc())
    )
    for row in events:
        log.append(
            _Draft(
                ContextEntry(
                    kind="log",
                    id=str(row.id),
                    title=row.title,
                    at=_iso(row.recorded_at),
                ),
                extra=row.body or "",
            )
        )

    focus_draft = None
    if purpose == "follow_up" and focus is not None:
        focus_draft = _Draft(focus)
    scoped, kept_focus = apply_home_scope(
        {"tasks": tasks, "commitments": commitments, "waiting": waiting, "log": log},
        focus_draft,
    )
    remembered = _memory_rows(
        session,
        purpose=purpose,
        now=now,
        query=query,
        tasks=scoped["tasks"],
        commitments=scoped["commitments"],
        focus=kept_focus,
    )
    context = HouseContext(
        schema_version=SCHEMA_VERSION,
        purpose=purpose,
        time=local.isoformat(timespec="minutes"),
        theme=theme_for_time(local),
        tasks=scoped["tasks"],
        commitments=scoped["commitments"],
        waiting=scoped["waiting"],
        log=scoped["log"],
        log_days=log_days,
        memory=MemorySlot(
            limit=limits.memory_limit,
            items=[
                MemoryContextItem(id=str(row.id), kind=row.kind, text=text, pinned=row.pinned)  # type: ignore[arg-type]
                for row, text in remembered
            ],
        ),
        focus=kept_focus,
        trimmed=False,
    )
    context = trim_to_budget(context, limits.token_budget)
    kept = {item.id for item in context.memory.items}
    for row, _text in remembered:
        if str(row.id) in kept:
            row.last_used_at = now
    _log_counts(context)
    return context


def _memory_rows(
    session: Session,
    *,
    purpose: Purpose,
    now: datetime,
    query: str | None,
    tasks: list[ContextEntry],
    commitments: list[ContextEntry],
    focus: ContextEntry | None,
) -> list[tuple[MemoryItem, str]]:
    if purpose == "smart_add":
        search = query or ""
    elif query:
        search = query
    elif focus is not None:
        search = focus.title
    else:
        search = " ".join(item.title for item in [*tasks[:8], *commitments[:8]])
    search = search[:500]
    limit = context_limits(session).memory_limit
    rows = retrieve_memories(session, search, now, limit=limit) if search.strip() else []
    chosen: list[tuple[MemoryItem, str]] = []
    for row in rows:
        shown = redact_for_model(row.text)
        if not shown:
            continue
        chosen.append((row, shown))
    return chosen
