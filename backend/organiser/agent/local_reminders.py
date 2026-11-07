"""Reminder cards. Rules choose the candidate. One completion decides the card.

The master switch defaults off, and so does each type. Master off prepares
nothing even when a type is saved on. Quiet hours, the daily caps, a pending
card, a paused house, and an assistant that is off all refuse before any
provider call. A disabled type is not sent. A card already waiting is left
where it is. Apply is still a separate tap, and it only adds the assessed note.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError, ProgrammingError
from sqlalchemy.orm import Session

from organiser.agent.cards import summarise
from organiser.agent.mistral import MistralUnavailable
from organiser.agent.reminder_assess import AssessmentRejected, assess
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
from organiser.services.system import assistant_effective, ensure_system_state

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
UNAVAILABLE = "The assistant is off. Nothing was assessed."
UNREACHABLE = "The assistant could not be reached. Nothing was prepared."
REJECTED = "The assessment could not be used. Nothing was prepared."
DECLINED = "Assessed. Nothing here was worth flagging."
ASSESSED = "Assessed. A card is waiting. Apply adds the note."


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


def _result(
    prepared: int,
    reason: str,
    *,
    called: bool = False,
    summary: str | None = None,
    assessment: str = "skipped",
) -> dict:
    return {
        "prepared": prepared,
        "reason": reason,
        "calls_assistant": called,
        "summary": summary,
        "assessment": assessment,
    }


def _assistant_on(session: Session, settings: Settings) -> bool:
    return assistant_effective(ensure_system_state(session), settings.assistant_enabled)


def _skipped_reason(skipped: list[str]) -> str:
    if len(skipped) == 1:
        return f"{TYPE_LABELS[skipped[0]]} are off. Nothing new was prepared."
    return "Those reminder types are off. Nothing new was prepared."


def _remembered_verdict(session: Session, local_now: datetime) -> str | None:
    """The last finished assessment, so a reload does not call the provider again."""
    run = session.scalars(
        select(AgentRun)
        .where(
            AgentRun.trigger.in_(tuple(TYPE_RULES.values())),
            AgentRun.status == "done",
            AgentRun.reply.is_not(None),
            AgentRun.finished_at >= local_now - timedelta(hours=72),
        )
        .order_by(AgentRun.finished_at.desc())
        .limit(1)
    ).first()
    if run is None or not run.reply:
        return None
    return run.reply


def prepare_local_reminder(session: Session, local_now: datetime, settings: Settings, client=None) -> dict:
    """One assessed note, a decline, or a reason. No call until the gates pass.

    The caller keeps the Decisions review off while the master switch is on, so
    this is the only reminder pipeline. A second call for the same item version
    does not call the provider again.
    """
    flags = reminder_flags(session)
    if not flags.master:
        return _result(0, "off")
    held = _hold(session, local_now, settings)
    if held == "A reminder is already waiting.":
        note = waiting_type_note(session, flags)
        return _result(0, note or held)
    if held:
        return _result(0, held)
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
            return _result(0, _skipped_reason(skipped))
        remembered = _remembered_verdict(session, local_now)
        if remembered:
            assessment = "declined" if remembered == DECLINED else "rejected"
            if remembered == ASSESSED:
                assessment = "assessed"
            return _result(0, remembered, assessment=assessment)
        return _result(0, "nothing due")
    if not _assistant_on(session, settings) or client is None:
        return _result(0, UNAVAILABLE, assessment="unavailable")
    from organiser.models import Commitment, Task

    model = Task if chosen.ref_type == "task" else Commitment
    row_model = session.get(model, chosen.ref_id)
    if row_model is None or outside_home(row_model.title):
        return _result(0, "nothing due")
    stamp = row_model.updated_at
    run = AgentRun(
        trigger=chosen.rule,
        window_key=chosen.window_key,
        status="running",
        searched=False,
        started_at=local_now,
    )
    session.add(run)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        return _result(0, "already assessed")
    run_id = run.id
    try:
        verdict = assess(client, settings, chosen, local_now.date())
    except MistralUnavailable:
        _drop_run(session, run_id)
        return _result(0, UNREACHABLE, called=True, assessment="unreachable")
    except AssessmentRejected:
        _close_run(session, run_id, local_now, REJECTED)
        return _result(0, REJECTED, called=True, assessment="rejected")
    blocked = _recheck(session, local_now, settings, chosen, stamp)
    if blocked:
        _close_run(session, run_id, local_now, blocked)
        return _result(0, blocked, called=True, assessment="rejected")
    if not verdict.worth_flagging:
        _close_run(session, run_id, local_now, DECLINED)
        return _result(0, DECLINED, called=True, assessment="declined")
    current = session.get(model, chosen.ref_id)
    if current is None:
        _close_run(session, run_id, local_now, "The item changed. Nothing was prepared.")
        return _result(0, "The item changed. Nothing was prepared.", called=True, assessment="rejected")
    changes = {"note": verdict.next_step, "dated": local_now.date().isoformat()}
    proposal = AgentProposal(
        run_id=run_id,
        origin="proactive",
        rule=chosen.rule,
        label="Assessed reminder",
        action="add_note",
        ref_type=chosen.ref_type,
        ref_id=chosen.ref_id,
        changes=changes,
        summary=summarise("add_note", changes, current),
        reason=verdict.rationale,
        ref_updated_at=current.updated_at,
        status="pending",
        created_at=local_now,
        memories_used=0,
    )
    session.add(proposal)
    _close_run(session, run_id, local_now, None)
    return _result(1, chosen.rule, called=True, summary=proposal.summary, assessment="assessed")


def _recheck(session: Session, local_now: datetime, settings: Settings, chosen, stamp) -> str | None:
    """Read the house again after the provider returns. A stale answer is not stored.

    The run cap is not applied again: this call already reserved its run.
    """
    session.expire_all()
    flags = reminder_flags(session)
    if not flags.master:
        return "Local reminders are off. Nothing was prepared."
    if not _assistant_on(session, settings):
        return UNAVAILABLE
    state = ensure_system_state(session)
    if state.paused:
        return "The house is paused."
    if not in_hours(local_now, PROACTIVE_HOURS):
        return "Quiet hours. Nothing is sent."
    from organiser.agent.rules import build_snapshot

    snapshot = build_snapshot(session, local_now, settings)
    if snapshot.proactive_today >= settings.agent_proactive_per_day:
        return "The daily reminder cap is spent."
    if snapshot.proactive_pending:
        return "A reminder is already waiting."
    name = RULE_TYPES.get(chosen.rule)
    if name is None or not flags.type_on(name):
        return _skipped_reason([name] if name else [])
    from organiser.models import Commitment, Task

    model = Task if chosen.ref_type == "task" else Commitment
    row = session.get(model, chosen.ref_id)
    if row is None or row.updated_at != stamp or outside_home(row.title):
        return "The item changed. Nothing was prepared."
    return None


def _close_run(session: Session, run_id, local_now: datetime, reply: str | None) -> None:
    run = session.get(AgentRun, run_id)
    if run is None:
        return
    run.status = "done"
    run.finished_at = local_now
    run.reply = reply
    session.commit()


def _drop_run(session: Session, run_id) -> None:
    """A provider failure does not rest the item, and it does not leave a card."""
    run = session.get(AgentRun, run_id)
    if run is not None and run.status == "running":
        session.delete(run)
    session.commit()
