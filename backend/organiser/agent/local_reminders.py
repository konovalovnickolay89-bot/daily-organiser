"""Local reminder cards. No Mistral call and no effect until Apply.

The house switch defaults off. Quiet hours, the daily caps, a pending card,
and a paused house all refuse. A second prepare for the same item version
does not add another card.
"""

from datetime import datetime

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


def reminders_enabled(session: Session) -> bool:
    """False when the switch is off or the table is not in this database."""
    try:
        row = session.get(ReminderControl, 1)
    except ProgrammingError:
        session.rollback()
        return False
    return bool(row and row.enabled)


def set_reminders_enabled(session: Session, enabled: bool, now: datetime) -> ReminderControl:
    """Save the switch. Creating the row still leaves it off until ``enabled`` is true."""
    row = session.get(ReminderControl, 1)
    if row is None:
        row = ReminderControl(id=1, enabled=False, updated_at=now)
        session.add(row)
        session.flush()
    if row.enabled == enabled:
        return row
    row.enabled = enabled
    row.updated_at = now
    if enabled:
        title = "Local reminders on"
        body = "Saved. A later look may prepare one card. Nothing is sent until Apply."
    else:
        title = "Local reminders off"
        body = "Saved. No local card will be prepared. Nothing was sent."
    record_event(session, kind="note", title=title, body=body, owner=DEFAULT_OWNER)
    return row


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


def prepare_local_reminder(session: Session, local_now: datetime, settings: Settings) -> dict:
    """One pending note, or a reason and nothing written. Never calls a provider."""
    if not reminders_enabled(session):
        return {"prepared": 0, "reason": "off", "calls_assistant": False}
    held = _hold(session, local_now, settings)
    if held:
        return {"prepared": 0, "reason": held, "calls_assistant": False}
    chosen = None
    for candidate in stale_candidates(session, local_now):
        if outside_home(candidate.title):
            continue
        if candidate.rule not in ("doing_stalled", "overdue_lingering", "commitment_due_soon"):
            continue
        chosen = candidate
        break
    if chosen is None:
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
