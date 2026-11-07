"""Local reminder cards. No Mistral call and no effect until Apply.

The master switch defaults off, and so does each type. Master off prepares
nothing even when a type is saved on. Quiet hours, the daily caps, a pending
card, and a paused house all refuse. A disabled type does not gain a new card,
and a card already waiting is left where it is.
"""

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError, ProgrammingError
from sqlalchemy.orm import Session

from organiser.agent.cards import summarise
from organiser.agent.rules import (
    PROACTIVE_HOURS,
    in_hours,
    runs_today,
    stale_candidates,
)
from organiser.agent.runner import outside_home
from organiser.config import Settings
from organiser.domain import DEFAULT_OWNER
from organiser.models import AgentProposal, AgentRun, ReminderControl
from organiser.services.events import record_event
from organiser.services.system import ensure_system_state

TYPE_RULES = {
    "overdue": "overdue_lingering",
    "stalled": "doing_stalled",
    "upcoming": "commitment_due_soon",
}
RULE_TYPES = {rule: name for name, rule in TYPE_RULES.items()}
TYPE_LABELS = {
    "overdue": "Overdue tasks",
    "stalled": "Stalled items",
    "upcoming": "Upcoming commitments",
}


class TypesUnavailable(Exception):
    """The type columns are not in this database. Nothing was turned on."""


@dataclass(frozen=True)
class ReminderFlags:
    master: bool = False
    overdue: bool = False
    stalled: bool = False
    upcoming: bool = False
    types_ready: bool = False

    def type_on(self, name: str) -> bool:
        return bool(getattr(self, name))

    def as_words(self) -> dict[str, str]:
        return {
            "local_reminders": "on" if self.master else "off",
            "reminder_overdue": "on" if self.overdue else "off",
            "reminder_stalled": "on" if self.stalled else "off",
            "reminder_upcoming": "on" if self.upcoming else "off",
            "reminder_types_ready": self.types_ready,
        }


def reminder_flags(session: Session) -> ReminderFlags:
    """Master and types. A missing table or missing columns read as off."""
    try:
        row = session.get(ReminderControl, 1)
    except ProgrammingError:
        session.rollback()
        return _legacy_flags(session)
    if row is None:
        return ReminderFlags(types_ready=True)
    return ReminderFlags(
        master=bool(row.enabled),
        overdue=bool(row.overdue),
        stalled=bool(row.stalled),
        upcoming=bool(row.upcoming),
        types_ready=True,
    )


def _legacy_flags(session: Session) -> ReminderFlags:
    try:
        raw = session.execute(text("SELECT enabled FROM reminder_control WHERE id = 1")).scalar()
    except ProgrammingError:
        session.rollback()
        return ReminderFlags()
    return ReminderFlags(master=bool(raw), types_ready=False)


def reminders_enabled(session: Session) -> bool:
    """False when the master switch is off or the table is not in this database."""
    return reminder_flags(session).master


def set_reminder_flags(
    session: Session,
    now: datetime,
    *,
    enabled: bool | None = None,
    overdue: bool | None = None,
    stalled: bool | None = None,
    upcoming: bool | None = None,
) -> ReminderFlags:
    """Save only the switches that were sent. Omitted types stay as they are."""
    current = reminder_flags(session)
    if not current.types_ready and any(value is not None for value in (overdue, stalled, upcoming)):
        raise TypesUnavailable()
    if not current.types_ready:
        _set_legacy_master(session, now, bool(enabled))
        return reminder_flags(session)
    row = session.get(ReminderControl, 1)
    if row is None:
        row = ReminderControl(id=1, enabled=False, overdue=False, stalled=False, upcoming=False, updated_at=now)
        session.add(row)
        session.flush()
    changes: list[str] = []
    if enabled is not None and row.enabled != enabled:
        row.enabled = enabled
        changes.append("Local reminders on" if enabled else "Local reminders off")
    for name, value in (("overdue", overdue), ("stalled", stalled), ("upcoming", upcoming)):
        if value is None or getattr(row, name) == value:
            continue
        setattr(row, name, value)
        state = "on" if value else "off"
        changes.append(f"{TYPE_LABELS[name]} {state}")
    if not changes:
        return reminder_flags(session)
    row.updated_at = now
    record_event(
        session,
        kind="note",
        title=changes[0],
        body="Saved for the house. A waiting card was not removed. Nothing is sent until Apply.",
        owner=DEFAULT_OWNER,
    )
    return reminder_flags(session)


def _set_legacy_master(session: Session, now: datetime, enabled: bool) -> None:
    try:
        raw = session.execute(text("SELECT enabled FROM reminder_control WHERE id = 1")).scalar()
    except ProgrammingError:
        session.rollback()
        raise TypesUnavailable() from None
    if raw is None:
        session.execute(
            text("INSERT INTO reminder_control (id, enabled, updated_at) VALUES (1, :enabled, :now)"),
            {"enabled": enabled, "now": now},
        )
    elif bool(raw) != enabled:
        session.execute(
            text("UPDATE reminder_control SET enabled = :enabled, updated_at = :now WHERE id = 1"),
            {"enabled": enabled, "now": now},
        )
    else:
        return
    title = "Local reminders on" if enabled else "Local reminders off"
    record_event(
        session,
        kind="note",
        title=title,
        body="Saved. Type switches are not in this database yet, so they stay off.",
        owner=DEFAULT_OWNER,
    )


def _hold(session: Session, local_now: datetime, settings: Settings) -> str | None:
    state = ensure_system_state(session)
    if state.paused:
        return "The house is paused."
    if not in_hours(local_now, PROACTIVE_HOURS):
        return "Quiet hours. Nothing is sent."
    start_runs = runs_today(session, local_now, settings.house_timezone)
    if start_runs >= settings.agent_runs_per_day:
        return "The daily run cap is spent."
    from organiser.agent.rules import build_snapshot

    snapshot = build_snapshot(session, local_now, settings)
    if snapshot.proactive_today >= settings.agent_proactive_per_day:
        return "The daily reminder cap is spent."
    if snapshot.proactive_pending:
        return "A reminder is already waiting."
    return None


def waiting_type_note(session: Session, flags: ReminderFlags) -> str | None:
    """A pending card whose type is off stays. This only describes it."""
    pending = session.scalars(
        select(AgentProposal)
        .where(AgentProposal.origin == "proactive", AgentProposal.status == "pending")
        .order_by(AgentProposal.created_at.desc())
        .limit(1)
    ).first()
    if pending is None:
        return None
    name = RULE_TYPES.get(pending.rule)
    if name is None or flags.type_on(name):
        return None
    return (
        f"{TYPE_LABELS[name]} are off. A reminder of that type is still waiting, "
        "so the card was left in place and no new card was prepared."
    )


def prepare_local_reminder(session: Session, local_now: datetime, settings: Settings) -> dict:
    """One pending note, or a reason and nothing written. Never calls a provider."""
    flags = reminder_flags(session)
    if not flags.master:
        return {"prepared": 0, "reason": "off", "calls_assistant": False}
    held = _hold(session, local_now, settings)
    if held == "A reminder is already waiting.":
        note = waiting_type_note(session, flags)
        return {"prepared": 0, "reason": note or held, "calls_assistant": False}
    if held:
        return {"prepared": 0, "reason": held, "calls_assistant": False}
    chosen = None
    skipped: list[str] = []
    for candidate in stale_candidates(session, local_now):
        if outside_home(candidate.title):
            continue
        name = RULE_TYPES.get(candidate.rule)
        if name is None:
            continue
        if not flags.type_on(name):
            if name not in skipped:
                skipped.append(name)
            continue
        chosen = candidate
        break
    if chosen is None:
        if skipped:
            if len(skipped) == 1:
                reason = f"{TYPE_LABELS[skipped[0]]} are off. Nothing new was prepared."
            else:
                reason = "Those reminder types are off. Nothing new was prepared."
            return {"prepared": 0, "reason": reason, "calls_assistant": False}
        return {"prepared": 0, "reason": "nothing due", "calls_assistant": False}
    note = chosen.reason
    changes = {"note": note, "dated": local_now.date().isoformat()}
    row_model = None
    from organiser.models import Commitment, Task

    model = Task if chosen.ref_type == "task" else Commitment
    row_model = session.get(model, chosen.ref_id)
    if row_model is None:
        return {"prepared": 0, "reason": "nothing due", "calls_assistant": False}
    run = AgentRun(
        trigger=chosen.rule,
        window_key=chosen.window_key,
        status="done",
        searched=False,
        started_at=local_now,
        finished_at=local_now,
    )
    session.add(run)
    try:
        session.flush()
    except IntegrityError:
        session.rollback()
        return {"prepared": 0, "reason": "already prepared", "calls_assistant": False}
    proposal = AgentProposal(
        run_id=run.id,
        origin="proactive",
        rule=chosen.rule,
        label="Local reminder",
        action="add_note",
        ref_type=chosen.ref_type,
        ref_id=chosen.ref_id,
        changes=changes,
        summary=summarise("add_note", changes, row_model),
        reason="Prepared locally. Nothing is sent until Apply.",
        ref_updated_at=row_model.updated_at,
        status="pending",
        created_at=local_now,
        memories_used=0,
    )
    session.add(proposal)
    session.flush()
    return {"prepared": 1, "reason": chosen.rule, "calls_assistant": False, "summary": proposal.summary}
