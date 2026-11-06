"""The context a later Mistral read can take. Building it changes no row.

Smart Add sees three days of the house log. Catch-up sees seven. Memory is a
placeholder of ten empty slots. A hotel, a guest, a colleague, or an employer
is left out before the text is assembled.
"""

from datetime import datetime, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from organiser.agent.runner import outside_home
from organiser.config import get_settings
from organiser.models import AgentProposal, Commitment, Event, Task

MEMORY_LIMIT = 10
SMART_ADD_LOG_DAYS = 3
CATCH_UP_LOG_DAYS = 7
Purpose = Literal["smart_add", "catch_up"]


class ContextEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["task", "commitment", "waiting", "log"]
    id: str
    title: str
    status: str | None = None
    due_on: str | None = None
    at: str | None = None


class MemorySlot(BaseModel):
    """Reserved for a later memory. Nothing is read or written here yet."""

    model_config = ConfigDict(extra="forbid")

    limit: int
    items: list[ContextEntry]


class HouseContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    purpose: Purpose
    time: str
    theme: Literal["morning", "evening"]
    tasks: list[ContextEntry]
    commitments: list[ContextEntry]
    waiting: list[ContextEntry]
    log: list[ContextEntry]
    log_days: int
    memory: MemorySlot


def theme_for_time(local: datetime) -> Literal["morning", "evening"]:
    """Same split as the arrival screen: 05:00–16:59 morning, otherwise evening."""
    return "morning" if 5 <= local.hour < 17 else "evening"


def _in_house(*parts: str | None) -> bool:
    return not any(outside_home(part) for part in parts if part)


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=ZoneInfo("UTC"))
    return value.isoformat(timespec="seconds")


def build_context(session: Session, *, purpose: Purpose, now: datetime) -> HouseContext:
    """Assemble one context. Read only. The caller does not have to send it on."""
    settings = get_settings()
    local = now.astimezone(ZoneInfo(settings.house_timezone))
    log_days = SMART_ADD_LOG_DAYS if purpose == "smart_add" else CATCH_UP_LOG_DAYS
    since = local - timedelta(days=log_days)

    tasks: list[ContextEntry] = []
    for row in session.scalars(select(Task).where(Task.status != "done").order_by(Task.title.asc())):
        if not _in_house(row.title, row.detail):
            continue
        tasks.append(
            ContextEntry(
                kind="task",
                id=str(row.id),
                title=row.title,
                status=row.status,
                due_on=row.due_on.isoformat() if row.due_on else None,
            )
        )

    commitments: list[ContextEntry] = []
    for row in session.scalars(
        select(Commitment).where(Commitment.status == "open").order_by(Commitment.title.asc())
    ):
        if not _in_house(row.title, row.detail):
            continue
        commitments.append(
            ContextEntry(
                kind="commitment",
                id=str(row.id),
                title=row.title,
                status=row.status,
                due_on=row.due_on.isoformat() if row.due_on else None,
            )
        )

    waiting: list[ContextEntry] = []
    pending = session.scalars(
        select(AgentProposal).where(AgentProposal.status == "pending").order_by(AgentProposal.created_at.desc())
    )
    for row in pending:
        if not _in_house(row.summary, row.reason):
            continue
        waiting.append(
            ContextEntry(
                kind="waiting",
                id=str(row.id),
                title=row.summary,
                status=row.status,
                at=_iso(row.created_at),
            )
        )

    log: list[ContextEntry] = []
    events = session.scalars(
        select(Event).where(Event.recorded_at >= since).order_by(Event.recorded_at.desc())
    )
    for row in events:
        if not _in_house(row.title, row.body):
            continue
        log.append(
            ContextEntry(
                kind="log",
                id=str(row.id),
                title=row.title,
                at=_iso(row.recorded_at),
            )
        )

    return HouseContext(
        purpose=purpose,
        time=local.isoformat(timespec="minutes"),
        theme=theme_for_time(local),
        tasks=tasks,
        commitments=commitments,
        waiting=waiting,
        log=log,
        log_days=log_days,
        memory=MemorySlot(limit=MEMORY_LIMIT, items=[]),
    )
