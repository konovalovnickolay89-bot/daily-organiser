"""Catch-up after a gap, decided in code.

The arrival screen records a look. The first look after eight hours away, or
after an overnight gap, opens one pass of at most four cards. Quiet hours are
22:00–05:59 London: nothing is shown. A look in those hours does not spend a
gap that is already due, so the cards can still open at 06:00. A paused house
records nothing and shows nothing.

Each card is one dated note on one task or commitment. Apply writes that note.
Not now rests that item for 72 hours. Nothing is sent, bought, or booked.
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from organiser.agent.cards import DETAIL_LIMIT, clip, note_line, summarise, with_note
from organiser.config import get_settings
from organiser.domain import DEFAULT_OWNER
from organiser.models import CatchUpItem, CatchUpPass, Commitment, SystemState, Task
from organiser.services.events import record_event
from organiser.services.system import ensure_system_state

GAP = timedelta(hours=8)
COOLDOWN = timedelta(hours=72)
# 06:00 inclusive, 22:00 exclusive. Outside that is quiet (22:00–05:59).
WAKING = (6, 22)
STALLED_DAYS = 3
MAX_ITEMS = 4

_UTC = ZoneInfo("UTC")
_PRIORITY = {"high": 0, "medium": 1, "low": 2}
_MODELS = {"task": Task, "commitment": Commitment}


class CatchUpNotFound(Exception):
    pass


class CatchUpClosed(Exception):
    pass


class CatchUpPaused(Exception):
    pass


class CatchUpStale(Exception):
    """The row changed or went away. The card is marked stale."""


@dataclass(frozen=True)
class _Draft:
    rule: str
    label: str
    ref_type: str
    ref_id: UUID
    title: str
    note: str
    reason: str
    ref_updated_at: datetime
    rank: tuple


class _Titled:
    def __init__(self, title: str) -> None:
        self.title = title


def is_quiet(local: datetime) -> bool:
    return not (WAKING[0] <= local.hour < WAKING[1])


def gap_due(previous: datetime, local: datetime) -> bool:
    """True after eight hours, or when the previous look was on an earlier London date."""
    prev = previous.astimezone(local.tzinfo)
    if local - prev >= GAP:
        return True
    return prev.date() < local.date()


def _span(days: int) -> str:
    return "1 day" if days == 1 else f"{days} days"


def _local(now: datetime) -> datetime:
    return now.astimezone(ZoneInfo(get_settings().house_timezone))


def _locked_state(session: Session) -> SystemState:
    row = session.get(SystemState, 1, with_for_update=True)
    if row is None:
        ensure_system_state(session)
        session.flush()
        row = session.get(SystemState, 1, with_for_update=True)
    return row


def _same_instant(left: datetime | None, right: datetime | None) -> bool:
    if left is None or right is None:
        return False
    return left.astimezone(_UTC) == right.astimezone(_UTC)


def _pending(session: Session) -> list[CatchUpItem]:
    return list(
        session.scalars(
            select(CatchUpItem).where(CatchUpItem.status == "pending").order_by(CatchUpItem.position.asc())
        ).all()
    )


def _has_pending(session: Session) -> bool:
    return session.scalar(select(CatchUpItem.id).where(CatchUpItem.status == "pending").limit(1)) is not None


def _resting(session: Session, now: datetime) -> set[tuple[str, UUID]]:
    cutoff = now - COOLDOWN
    rows = session.execute(
        select(CatchUpItem.ref_type, CatchUpItem.ref_id).where(
            CatchUpItem.status == "dismissed",
            CatchUpItem.decided_at.is_not(None),
            CatchUpItem.decided_at > cutoff,
        )
    )
    return {(ref_type, ref_id) for ref_type, ref_id in rows}


def _skip(session: Session, now: datetime) -> set[tuple[str, UUID]]:
    waiting = {
        (ref_type, ref_id)
        for ref_type, ref_id in session.execute(
            select(CatchUpItem.ref_type, CatchUpItem.ref_id).where(CatchUpItem.status == "pending")
        )
    }
    return waiting | _resting(session, now)


def choose_items(session: Session, local: datetime) -> tuple[_Draft, ...]:
    """The cards for one pass, most pressing first, capped.

    One row appears once. Overdue and due-today tasks come before a stalled
    task, then commitments due today or tomorrow, then anything else still
    unfinished on the brief.
    """
    today = local.date()
    tomorrow = today + timedelta(days=1)
    drafts: list[_Draft] = []

    overdue = session.scalars(select(Task).where(Task.status != "done", Task.due_on < today)).all()
    for row in overdue:
        days = (today - row.due_on).days
        span = _span(days)
        drafts.append(
            _Draft(
                rule="overdue",
                label="Overdue",
                ref_type="task",
                ref_id=row.id,
                title=row.title,
                note=f"{span} overdue.",
                reason=f"{span} overdue",
                ref_updated_at=row.updated_at,
                rank=(0, -days, _PRIORITY.get(row.priority, 9), row.title.lower()),
            )
        )

    due_today = session.scalars(select(Task).where(Task.status != "done", Task.due_on == today)).all()
    for row in due_today:
        drafts.append(
            _Draft(
                rule="due_today",
                label="Due today",
                ref_type="task",
                ref_id=row.id,
                title=row.title,
                note="Due today.",
                reason="Due today",
                ref_updated_at=row.updated_at,
                rank=(1, _PRIORITY.get(row.priority, 9), row.title.lower()),
            )
        )

    doing = session.scalars(select(Task).where(Task.status == "doing")).all()
    for row in doing:
        days = (local - row.updated_at.astimezone(local.tzinfo)).days
        if days < STALLED_DAYS:
            continue
        span = _span(days)
        drafts.append(
            _Draft(
                rule="stalled",
                label="In progress",
                ref_type="task",
                ref_id=row.id,
                title=row.title,
                note=f"No update for {span}.",
                reason=f"In progress, no update for {span}",
                ref_updated_at=row.updated_at,
                rank=(2, -days, row.title.lower()),
            )
        )

    soon = session.scalars(
        select(Commitment).where(
            Commitment.status == "open",
            Commitment.due_on >= today,
            Commitment.due_on <= tomorrow,
        )
    ).all()
    for row in soon:
        if row.due_on == today:
            note, reason = "Due today.", "Due today"
        else:
            note, reason = "Due tomorrow.", "Due tomorrow"
        drafts.append(
            _Draft(
                rule="commitment_due",
                label="Commitment",
                ref_type="commitment",
                ref_id=row.id,
                title=row.title,
                note=note,
                reason=reason,
                ref_updated_at=row.updated_at,
                rank=(3, row.due_on.isoformat(), row.title.lower()),
            )
        )

    undated = session.scalars(select(Task).where(Task.status != "done", Task.due_on.is_(None))).all()
    for row in undated:
        drafts.append(
            _Draft(
                rule="brief",
                label="On the brief",
                ref_type="task",
                ref_id=row.id,
                title=row.title,
                note="Still on the brief, with no date.",
                reason="On the brief, not finished",
                ref_updated_at=row.updated_at,
                rank=(4, _PRIORITY.get(row.priority, 9), row.title.lower()),
            )
        )

    open_commitments = session.scalars(select(Commitment).where(Commitment.status == "open")).all()
    for row in open_commitments:
        due = row.due_on.isoformat() if row.due_on is not None else "9999-12-31"
        drafts.append(
            _Draft(
                rule="brief",
                label="On the brief",
                ref_type="commitment",
                ref_id=row.id,
                title=row.title,
                note="Still open on the brief.",
                reason="Open on the brief",
                ref_updated_at=row.updated_at,
                rank=(5, due, row.title.lower()),
            )
        )

    skip = _skip(session, local)
    chosen: list[_Draft] = []
    seen: set[tuple[str, UUID]] = set()
    for draft in sorted(drafts, key=lambda item: item.rank):
        key = (draft.ref_type, draft.ref_id)
        if key in seen or key in skip:
            continue
        seen.add(key)
        chosen.append(draft)
        if len(chosen) == MAX_ITEMS:
            break
    return tuple(chosen)


def _window_key(previous: datetime) -> str:
    return f"gap:{previous.astimezone(_UTC).isoformat()}"


def _open_pass(session: Session, local: datetime, previous: datetime) -> None:
    """Insert one pass for this gap. A second screen finds the same window and stops."""
    window_key = _window_key(previous)
    if session.scalar(select(CatchUpPass.id).where(CatchUpPass.window_key == window_key)) is not None:
        return
    drafts = choose_items(session, local)
    if not drafts:
        return
    try:
        with session.begin_nested():
            pass_row = CatchUpPass(window_key=window_key, opened_at=local, from_looked_at=previous)
            session.add(pass_row)
            session.flush()
            for position, draft in enumerate(drafts):
                changes = {"dated": local.date().isoformat(), "note": draft.note}
                session.add(
                    CatchUpItem(
                        pass_id=pass_row.id,
                        position=position,
                        rule=draft.rule,
                        label=draft.label,
                        action="add_note",
                        ref_type=draft.ref_type,
                        ref_id=draft.ref_id,
                        changes=changes,
                        summary=summarise("add_note", changes, _Titled(draft.title)),
                        reason=draft.reason,
                        ref_updated_at=draft.ref_updated_at,
                        status="pending",
                        created_at=local,
                    )
                )
            session.flush()
    except IntegrityError:
        return


def record_look(session: Session, now: datetime) -> dict:
    """Record a look and, when a gap qualifies, open one pass.

    The system row is locked, so two tabs share one pass.
    """
    local = _local(now)
    row = _locked_state(session)
    if row.paused:
        return _view(local, paused=True, quiet=is_quiet(local), items=[])

    quiet = is_quiet(local)
    previous = row.last_looked_at
    due = previous is not None and gap_due(previous, local)
    # A catch-up that comes due overnight waits until 06:00. Moving the look
    # now would spend that gap before the cards can be shown.
    if quiet:
        if not due:
            row.last_looked_at = local
        return _view(local, paused=False, quiet=True, items=[])

    if due and not _has_pending(session):
        _open_pass(session, local, previous)
    row.last_looked_at = local
    return _view(local, paused=False, quiet=False, items=_pending(session))


def read_catchup(session: Session, now: datetime) -> dict:
    """What the strip may show. Does not record a look and does not open a pass."""
    local = _local(now)
    row = ensure_system_state(session)
    quiet = is_quiet(local)
    if row.paused or quiet:
        return _view(local, paused=row.paused, quiet=quiet, items=[])
    return _view(local, paused=False, quiet=False, items=_pending(session))


def _view(local: datetime, *, paused: bool, quiet: bool, items: list[CatchUpItem]) -> dict:
    return {
        "paused": paused,
        "quiet": quiet,
        "as_of": local,
        "house_date": local.date(),
        "items": items,
    }


def _stale(item: CatchUpItem, now: datetime) -> CatchUpStale:
    item.status = "stale"
    item.decided_at = now
    return CatchUpStale(str(item.id))


def apply_item(session: Session, item_id: UUID, now: datetime) -> tuple[CatchUpItem, dict]:
    """Append the card's note to one task or commitment. Nothing else is written."""
    if ensure_system_state(session).paused:
        raise CatchUpPaused()
    item = session.get(CatchUpItem, item_id, with_for_update=True)
    if item is None:
        raise CatchUpNotFound(str(item_id))
    if item.status != "pending":
        raise CatchUpClosed(item.status)
    if item.action != "add_note" or item.ref_type not in _MODELS:
        raise _stale(item, now)

    found = session.get(_MODELS[item.ref_type], item.ref_id, with_for_update=True)
    if found is None or not _same_instant(found.updated_at, item.ref_updated_at):
        raise _stale(item, now)

    changes = dict(item.changes or {})
    try:
        noted_on = date.fromisoformat(str(changes["dated"]))
        note = " ".join(str(changes["note"]).split())
    except (KeyError, ValueError, TypeError):
        raise _stale(item, now) from None
    if not note:
        raise _stale(item, now)

    detail = with_note(found.detail, note_line(noted_on, note))
    if len(detail) > DETAIL_LIMIT:
        raise _stale(item, now)

    found.detail = detail
    found.updated_at = now
    item.status = "applied"
    item.decided_at = now
    record_event(
        session,
        kind=item.ref_type,
        title=clip(f"Catch-up: {item.summary}", 200),
        body=f"From catch-up ({item.label}). {item.reason}. Nothing outside the house log was changed.",
        owner=DEFAULT_OWNER,
    )
    return item, {"ref_type": item.ref_type, "ref_id": found.id, "summary": item.summary}


def dismiss_item(session: Session, item_id: UUID, now: datetime) -> CatchUpItem:
    """Not now. The item rests for 72 hours. The task or commitment is unchanged."""
    if ensure_system_state(session).paused:
        raise CatchUpPaused()
    item = session.get(CatchUpItem, item_id, with_for_update=True)
    if item is None:
        raise CatchUpNotFound(str(item_id))
    if item.status != "pending":
        raise CatchUpClosed(item.status)
    item.status = "dismissed"
    item.decided_at = now
    return item
