"""When the assistant may speak on its own. Times are Europe/London unless stated."""

from datetime import date, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy.exc import IntegrityError

from agent_fakes import london
from organiser.agent.rules import (
    COOLDOWN,
    Candidate,
    Snapshot,
    next_look,
    proactive_due,
    stale_candidates,
    stale_reason,
)
from organiser.models import AgentProposal, AgentRun, Commitment, Task

MONDAY_8 = london(2026, 11, 2, 8, 0)


def _candidate(**overrides) -> Candidate:
    values = {
        "rule": "overdue_lingering",
        "ref_type": "task",
        "ref_id": uuid4(),
        "title": "Book the boiler service",
        "status": "todo",
        "due_on": date(2026, 10, 30),
        "ref_updated_at": london(2026, 10, 25, 9, 0),
        "reason": "3 days overdue",
    }
    values.update(overrides)
    return Candidate(**values)


def _snapshot(**overrides) -> Snapshot:
    values = {
        "enabled": True,
        "paused": False,
        "runs_today": 0,
        "proactive_today": 0,
        "proactive_pending": False,
        "morning_claimed": False,
        "candidates": (),
    }
    values.update(overrides)
    return Snapshot(**values)


def _due(now: datetime, **overrides):
    return proactive_due(now, _snapshot(**overrides), runs_per_day=12, proactive_per_day=3)


# --- proactive_due ----------------------------------------------------------


@pytest.mark.parametrize(
    ("hour", "minute", "expected"),
    [(5, 59, None), (6, 0, "morning_review"), (10, 59, "morning_review"), (11, 0, None)],
)
def test_morning_review_window(hour, minute, expected):
    due = _due(london(2026, 11, 2, hour, minute))
    assert (due.trigger if due else None) == expected


def test_morning_review_is_keyed_to_the_house_date_and_capped_at_two():
    due = _due(MONDAY_8)
    assert due.window_key == "2026-11-02"
    assert due.label == "Morning review"
    assert due.max_proposals == 2
    assert due.candidate is None


def test_morning_review_runs_once_a_day():
    assert _due(MONDAY_8, morning_claimed=True) is None


def test_nothing_while_paused_or_switched_off():
    candidate = _candidate()
    assert _due(MONDAY_8, paused=True, candidates=(candidate,)) is None
    assert _due(london(2026, 11, 2, 14, 0), enabled=False, candidates=(candidate,)) is None


@pytest.mark.parametrize(
    ("hour", "minute", "is_due"),
    [(5, 59, False), (6, 0, True), (21, 59, True), (22, 0, False), (23, 30, False), (2, 0, False)],
)
def test_quiet_hours_hold_back_stale_items(hour, minute, is_due):
    due = _due(london(2026, 11, 2, hour, minute), morning_claimed=True, candidates=(_candidate(),))
    assert (due is not None) is is_due


def test_stale_item_follows_the_morning_review_with_one_proposal():
    candidate = _candidate()
    due = _due(london(2026, 11, 2, 9, 30), morning_claimed=True, candidates=(candidate,))
    assert due.trigger == "overdue_lingering"
    assert due.window_key == candidate.window_key
    assert due.window_key.endswith("#1")
    assert due.label == "3 days overdue"
    assert due.max_proposals == 1
    assert due.candidate is candidate


def test_three_proactive_proposals_a_day():
    assert _due(MONDAY_8, proactive_today=3) is None
    assert _due(MONDAY_8, proactive_today=2).max_proposals == 1
    assert _due(london(2026, 11, 2, 15, 0), proactive_today=3, candidates=(_candidate(),)) is None


def test_one_proactive_card_at_a_time():
    assert _due(london(2026, 11, 2, 15, 0), proactive_pending=True, candidates=(_candidate(),)) is None


def test_runs_cap_covers_every_trigger():
    assert _due(MONDAY_8, runs_today=12) is None
    assert _due(MONDAY_8, runs_today=11) is not None


def test_summer_time_uses_london_civil_time():
    utc = ZoneInfo("UTC")
    # 05:00 UTC on 15 July is 06:00 BST: the morning window has opened.
    opened = _due(datetime(2026, 7, 15, 5, 0, tzinfo=utc).astimezone(ZoneInfo("Europe/London")))
    assert opened.trigger == "morning_review"
    assert opened.window_key == "2026-07-15"
    # 04:59 UTC is 05:59 BST: still quiet.
    assert _due(datetime(2026, 7, 15, 4, 59, tzinfo=utc).astimezone(ZoneInfo("Europe/London"))) is None


# --- stale_reason -----------------------------------------------------------


def _row(**fields):
    values = {"status": "todo", "due_on": None, "updated_at": MONDAY_8}
    values.update(fields)
    return SimpleNamespace(**values)


def test_doing_stalled_at_three_days():
    assert stale_reason("doing_stalled", MONDAY_8, _row(status="doing", updated_at=MONDAY_8 - timedelta(days=3))) == (
        "In progress, no update for 3 days"
    )
    almost = MONDAY_8 - timedelta(days=3) + timedelta(minutes=1)
    assert stale_reason("doing_stalled", MONDAY_8, _row(status="doing", updated_at=almost)) is None
    assert stale_reason("doing_stalled", MONDAY_8, _row(status="todo", updated_at=MONDAY_8 - timedelta(days=9))) is None


def test_overdue_lingering_at_two_days():
    today = MONDAY_8.date()
    assert stale_reason("overdue_lingering", MONDAY_8, _row(due_on=today - timedelta(days=2))) == "2 days overdue"
    assert stale_reason("overdue_lingering", MONDAY_8, _row(due_on=today - timedelta(days=1))) is None
    assert stale_reason("overdue_lingering", MONDAY_8, _row(status="done", due_on=today - timedelta(days=5))) is None
    assert stale_reason("overdue_lingering", MONDAY_8, _row(due_on=None)) is None


def test_commitment_due_today_or_tomorrow():
    today = MONDAY_8.date()
    assert stale_reason("commitment_due_soon", MONDAY_8, _row(status="open", due_on=today)) == "Due today"
    assert stale_reason("commitment_due_soon", MONDAY_8, _row(status="open", due_on=today + timedelta(days=1))) == (
        "Due tomorrow"
    )
    assert stale_reason("commitment_due_soon", MONDAY_8, _row(status="open", due_on=today + timedelta(days=2))) is None
    assert stale_reason("commitment_due_soon", MONDAY_8, _row(status="kept", due_on=today)) is None


# --- next_look: Not now rests an item for 72 hours, twice -------------------


def _run(started: datetime, finished: datetime | None = None):
    return SimpleNamespace(id=uuid4(), started_at=started, finished_at=finished or started)


def _proposal(status: str, decided: datetime | None = None):
    return SimpleNamespace(status=status, decided_at=decided)


def test_first_look_is_free():
    assert next_look([], [], MONDAY_8) == 1


def test_a_waiting_card_holds_the_item():
    assert next_look([_run(MONDAY_8)], [_proposal("pending")], MONDAY_8 + timedelta(days=9)) is None


def test_not_now_rests_the_item_for_72_hours():
    dismissed = MONDAY_8 + timedelta(minutes=5)
    runs = [_run(MONDAY_8)]
    proposals = [_proposal("dismissed", dismissed)]
    assert next_look(runs, proposals, dismissed + COOLDOWN - timedelta(minutes=1)) is None
    assert next_look(runs, proposals, dismissed + COOLDOWN + timedelta(minutes=1)) == 2


def test_a_look_with_nothing_proposed_also_rests():
    runs = [_run(MONDAY_8, MONDAY_8 + timedelta(seconds=20))]
    assert next_look(runs, [], MONDAY_8 + timedelta(hours=71)) is None
    assert next_look(runs, [], MONDAY_8 + timedelta(hours=73)) == 2


def test_after_two_looks_the_item_waits_until_it_changes():
    runs = [_run(MONDAY_8), _run(MONDAY_8 + timedelta(days=4))]
    assert next_look(runs, [], MONDAY_8 + timedelta(days=30)) is None


# --- stale_candidates against Postgres --------------------------------------


def _task(db, title, *, status="todo", due_on=None, updated_at=MONDAY_8 - timedelta(days=1)):
    row = Task(title=title, status=status, due_on=due_on, priority="medium", owner="Nick", updated_at=updated_at)
    db.add(row)
    db.flush()
    return row


def test_candidates_rank_and_one_rule_per_item(db):
    today = MONDAY_8.date()
    bulb = _task(db, "Replace the hallway bulb", status="doing", due_on=today - timedelta(days=4),
                 updated_at=MONDAY_8 - timedelta(days=5))
    boiler = _task(db, "Book the boiler service", due_on=today - timedelta(days=3))
    _task(db, "Put the bins out", due_on=today)
    _task(db, "Water the houseplants", due_on=today - timedelta(days=6), status="done")
    key = Commitment(title="Return the spare key", status="open", owner="Nick", due_on=today + timedelta(days=1),
                     updated_at=MONDAY_8 - timedelta(days=2))
    db.add(key)
    db.commit()

    candidates = stale_candidates(db, MONDAY_8)
    assert [(c.rule, c.title) for c in candidates] == [
        ("doing_stalled", "Replace the hallway bulb"),
        ("overdue_lingering", "Book the boiler service"),
        ("commitment_due_soon", "Return the spare key"),
    ]
    assert candidates[0].reason == "In progress, no update for 5 days"
    assert candidates[0].ref_id == bulb.id
    assert candidates[1].ref_id == boiler.id
    assert candidates[2].reason == "Due tomorrow"
    assert all(c.look == 1 for c in candidates)


def test_an_item_with_a_waiting_proposal_is_left_alone(db):
    boiler = _task(db, "Book the boiler service", due_on=MONDAY_8.date() - timedelta(days=3))
    run = AgentRun(trigger="feed", window_key="feed:x", status="done", started_at=MONDAY_8)
    db.add(run)
    db.flush()
    db.add(
        AgentProposal(run_id=run.id, origin="feed", rule="feed", label="From your note", action="update_task",
                      ref_type="task", ref_id=boiler.id, changes={"status": "done"}, summary="x", reason="y",
                      ref_updated_at=boiler.updated_at, created_at=MONDAY_8)
    )
    db.commit()
    assert stale_candidates(db, MONDAY_8) == ()


def test_dismissed_item_returns_after_72_hours_then_rests_for_good(db):
    boiler = _task(db, "Book the boiler service", due_on=MONDAY_8.date() - timedelta(days=3))
    db.commit()
    first = stale_candidates(db, MONDAY_8)[0]

    def look(candidate, at, decided):
        run = AgentRun(trigger=candidate.rule, window_key=candidate.window_key, status="done", started_at=at,
                       finished_at=at)
        db.add(run)
        db.flush()
        db.add(
            AgentProposal(run_id=run.id, origin="proactive", rule=candidate.rule, label=candidate.reason,
                          action="update_task", ref_type="task", ref_id=boiler.id, changes={"status": "done"},
                          summary="x", reason="y", ref_updated_at=boiler.updated_at, created_at=at,
                          status="dismissed", decided_at=decided)
        )
        db.commit()

    look(first, MONDAY_8, MONDAY_8 + timedelta(minutes=10))
    assert stale_candidates(db, MONDAY_8 + timedelta(hours=72)) == ()
    later = MONDAY_8 + timedelta(hours=72, minutes=11)
    second = stale_candidates(db, later)[0]
    assert second.look == 2
    assert second.window_key.endswith("#2")
    assert second.base_key == first.base_key

    look(second, later, later + timedelta(minutes=1))
    assert stale_candidates(db, later + timedelta(days=10)) == ()

    # Nick edits the task: a new version, so the assistant may look once more.
    boiler.updated_at = later + timedelta(days=1)
    db.commit()
    fresh = stale_candidates(db, later + timedelta(days=10))[0]
    assert fresh.look == 1
    assert fresh.base_key != first.base_key


def test_one_run_per_window(db):
    db.add(AgentRun(trigger="morning_review", window_key="2026-11-02", status="done", started_at=MONDAY_8))
    db.commit()
    db.add(AgentRun(trigger="morning_review", window_key="2026-11-02", status="running", started_at=MONDAY_8))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
