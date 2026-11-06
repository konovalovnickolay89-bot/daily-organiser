"""The five functions Mistral may call. Every refusal is enforced here, not in the prompt."""

from datetime import date, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select

from agent_fakes import london
from organiser.agent.functions import RunContext, dispatch
from organiser.models import AgentProposal, AgentRun, Commitment, SystemState, Task

MONDAY_8 = london(2026, 11, 2, 8, 0)
TODAY = MONDAY_8.date()
FRIDAY = date(2026, 11, 6)


@pytest.fixture
def ctx(db):
    def make(*, now=MONDAY_8, max_proposals=3, origin="feed", rule="feed"):
        run = AgentRun(trigger=rule, window_key=f"test:{uuid4()}", status="running", started_at=now)
        db.add(run)
        db.flush()
        return RunContext(
            session=db,
            now=now,
            tz_name="Europe/London",
            run=run,
            origin=origin,
            rule=rule,
            label="From your note",
            max_proposals=max_proposals,
        )

    return make


def _task(db, title, **fields):
    values = {"status": "todo", "priority": "medium", "owner": "Nick", "updated_at": MONDAY_8 - timedelta(days=1)}
    values.update(fields)
    row = Task(title=title, **values)
    db.add(row)
    db.flush()
    return row


def _commitment(db, title, **fields):
    values = {"status": "open", "owner": "Nick", "updated_at": MONDAY_8 - timedelta(days=1)}
    values.update(fields)
    row = Commitment(title=title, **values)
    db.add(row)
    db.flush()
    return row


def _propose(context, **arguments):
    arguments.setdefault("reason", "Filters are needed before the service.")
    return dispatch(context, "propose_change", arguments)


# --- reads ------------------------------------------------------------------


def test_get_state_counts_and_the_next_seven_days_across_a_month_end(db, ctx):
    saturday = london(2026, 11, 28, 9, 0)
    _task(db, "Overdue", due_on=date(2026, 11, 20))
    _task(db, "Doing", status="doing", due_on=date(2026, 11, 28))
    _task(db, "Two on the 30th", due_on=date(2026, 11, 30))
    _task(db, "Also on the 30th", due_on=date(2026, 11, 30))
    _task(db, "December", due_on=date(2026, 12, 1))
    _task(db, "Done already", status="done", due_on=date(2026, 12, 1))
    _commitment(db, "Pay the council tax", due_on=date(2026, 12, 1))
    _commitment(db, "Kept one", status="kept", due_on=date(2026, 12, 1))

    state = dispatch(ctx(now=saturday), "get_state", "{}")
    assert state["ok"] is True
    assert state["house_date"] == "2026-11-28"
    assert state["weekday"] == "Saturday"
    assert state["paused"] is False
    assert state["counts"] == {
        "tasks_todo": 4,
        "tasks_doing": 1,
        "tasks_overdue": 1,
        "tasks_due_today": 1,
        "commitments_open": 1,
        "proposals_waiting": 0,
    }
    assert state["next_7_days"] == [
        {"date": "2026-11-28", "weekday": "Sat", "items": 1},
        {"date": "2026-11-29", "weekday": "Sun", "items": 0},
        {"date": "2026-11-30", "weekday": "Mon", "items": 2},
        {"date": "2026-12-01", "weekday": "Tue", "items": 2},
        {"date": "2026-12-02", "weekday": "Wed", "items": 0},
        {"date": "2026-12-03", "weekday": "Thu", "items": 0},
        {"date": "2026-12-04", "weekday": "Fri", "items": 0},
    ]


def test_search_finds_words_filters_and_puts_open_items_first(db, ctx):
    _task(db, "Book the boiler service", detail="Annual service.", due_on=FRIDAY)
    _task(db, "Bleed the radiators", detail="Before the boiler service.", status="done")
    _task(db, "Put the bins out", due_on=TODAY)
    _commitment(db, "Boiler cover renewal", due_on=date(2026, 12, 1))
    context = ctx()

    found = dispatch(context, "search_items", {"text": "BOILER"})
    assert [item["title"] for item in found["items"]] == [
        "Book the boiler service",
        "Boiler cover renewal",
        "Bleed the radiators",
    ]
    assert found["items"][0]["kind"] == "task"
    assert found["items"][0]["priority"] == "medium"
    assert "priority" not in found["items"][1]

    tasks_only = dispatch(context, "search_items", {"text": "boiler", "kind": "task", "status": "todo"})
    assert [item["title"] for item in tasks_only["items"]] == ["Book the boiler service"]

    by_date = dispatch(context, "search_items", {"due_from": "2026-11-01", "due_to": "2026-11-03"})
    assert [item["title"] for item in by_date["items"]] == ["Put the bins out"]

    assert dispatch(context, "search_items", {"status": "open", "kind": "task"})["items"] == []
    assert len(dispatch(context, "search_items", {"limit": 2})["items"]) == 2


def test_search_treats_percent_as_a_letter(db, ctx):
    _task(db, "Check the 50% off filters")
    _task(db, "Water the houseplants")
    found = dispatch(ctx(), "search_items", {"text": "50%"})
    assert [item["title"] for item in found["items"]] == ["Check the 50% off filters"]


def test_search_refuses_unknown_arguments(ctx):
    result = dispatch(ctx(), "search_items", {"tag": "home"})
    assert result["ok"] is False
    assert "tag" in result["error"]


def test_get_item_returns_every_field_and_waiting_proposals(db, ctx):
    boiler = _task(db, "Book the boiler service", detail="Annual service.", due_on=FRIDAY)
    context = ctx()
    _propose(context, action="update_task", id=str(boiler.id), changes={"due_on": "2026-11-09"})

    result = dispatch(context, "get_item", {"kind": "task", "id": str(boiler.id)})
    assert result["ok"] is True
    assert result["item"]["detail"] == "Annual service."
    assert result["item"]["owner"] == "Nick"
    assert [proposal["summary"] for proposal in result["waiting_proposals"]] == [
        "Book the boiler service: due Fri 6 Nov → Mon 9 Nov"
    ]


def test_get_item_with_a_bad_or_unknown_id(ctx):
    bad = dispatch(ctx(), "get_item", {"kind": "task", "id": "not-an-id"})
    assert bad["ok"] is False and "not a valid id" in bad["error"]
    missing = dispatch(ctx(), "get_item", {"kind": "commitment", "id": str(uuid4())})
    assert missing["ok"] is False and "No commitment has the id" in missing["error"]


# --- proposals --------------------------------------------------------------


def test_create_task_stores_a_pending_card_and_changes_nothing_else(db, ctx):
    context = ctx()
    result = _propose(
        context,
        action="create_task",
        changes={"title": "Buy boiler filters", "due_on": "2026-11-06", "priority": "high"},
    )
    assert result["ok"] is True
    assert result["card"] == "New task: Buy boiler filters · due Fri 6 Nov · High priority"
    assert result["left_in_this_run"] == 2
    assert db.scalars(select(Task)).all() == []

    proposal = db.get(AgentProposal, result["proposal_id"])
    assert proposal.status == "pending"
    assert proposal.action == "create_task"
    assert proposal.changes == {"title": "Buy boiler filters", "due_on": "2026-11-06", "priority": "high"}
    assert proposal.reason == "Filters are needed before the service."
    assert proposal.created_at == MONDAY_8


@pytest.mark.parametrize(
    ("arguments", "phrase"),
    [
        ({"action": "update_task", "changes": {"owner": "Someone"}}, "The owner cannot be changed."),
        ({"action": "create_task", "changes": {"title": "Bins", "status": "done"}}, "create_task takes only"),
        ({"action": "create_commitment", "changes": {"title": "Pay", "priority": "high"}}, "Not: priority"),
        ({"action": "delete_task", "changes": {"title": "Bins"}}, "action"),
        ({"action": "create_task", "changes": {}}, "changes is empty"),
        ({"action": "create_task", "changes": {"title": "Bins", "due_on": "2026-11-01"}}, "is before today"),
        ({"action": "create_task", "changes": {"title": "Bins", "due_on": "next week"}}, "due_on"),
        ({"action": "create_task", "changes": {"title": "Bins"}, "id": str(uuid4())}, "Leave out id"),
        ({"action": "update_task", "changes": {"status": "done"}}, "id is required"),
        ({"action": "create_task", "changes": {"title": "Bins"}, "reason": "   "}, "reason is empty"),
    ],
)
def test_proposals_outside_the_allowlist_are_refused(db, ctx, arguments, phrase):
    result = _propose(ctx(), **arguments)
    assert result["ok"] is False
    assert phrase in result["error"]
    assert db.scalars(select(AgentProposal)).all() == []


def test_task_status_words_are_not_commitment_words(db, ctx):
    boiler = _task(db, "Book the boiler service")
    result = _propose(ctx(), action="update_task", id=str(boiler.id), changes={"status": "kept"})
    assert result["ok"] is False
    assert "status" in result["error"]


def test_duplicates_are_refused(db, ctx):
    _task(db, "Put the bins out", due_on=TODAY)
    context = ctx()
    open_task = _propose(context, action="create_task", changes={"title": "put the bins out"})
    assert open_task["ok"] is False and "already has that title" in open_task["error"]

    first = _propose(context, action="create_task", changes={"title": "Buy boiler filters"})
    assert first["ok"] is True
    again = _propose(ctx(), action="create_task", changes={"title": "Buy Boiler Filters"})
    assert again["ok"] is False and "already waiting" in again["error"]


def test_one_waiting_proposal_per_item(db, ctx):
    boiler = _task(db, "Book the boiler service", due_on=FRIDAY)
    context = ctx()
    assert _propose(context, action="update_task", id=str(boiler.id), changes={"due_on": "2026-11-09"})["ok"]
    second = _propose(context, action="update_task", id=str(boiler.id), changes={"status": "doing"})
    assert second["ok"] is False and "already waiting" in second["error"]


def test_updates_drop_unchanged_fields_and_refuse_a_no_op(db, ctx):
    boiler = _task(db, "Book the boiler service", due_on=FRIDAY, priority="medium")
    context = ctx()
    no_op = _propose(context, action="update_task", id=str(boiler.id), changes={"due_on": "2026-11-06"})
    assert no_op["ok"] is False and "already so" in no_op["error"]

    result = _propose(
        context,
        action="update_task",
        id=str(boiler.id),
        changes={"due_on": "2026-11-06", "priority": "high", "status": "doing"},
    )
    proposal = db.get(AgentProposal, result["proposal_id"])
    assert proposal.changes == {"priority": "high", "status": "doing"}
    assert proposal.summary == "Book the boiler service: To do → Doing; Medium → High priority"
    assert proposal.ref_updated_at == boiler.updated_at


def test_the_run_limit_is_enforced(ctx):
    context = ctx(max_proposals=1)
    assert _propose(context, action="create_task", changes={"title": "Buy filters"})["ok"]
    over = _propose(context, action="create_task", changes={"title": "Call the council"})
    assert over["ok"] is False and "limit for this run (1)" in over["error"]


def test_nothing_is_proposed_while_paused(db, ctx):
    db.add(SystemState(id=1, paused=True, activity="paused", status_text="Paused"))
    db.flush()
    result = _propose(ctx(), action="create_task", changes={"title": "Buy filters"})
    assert result["ok"] is False and "paused" in result["error"]
    note = dispatch(ctx(), "add_note", {"kind": "task", "id": str(uuid4()), "note": "x", "reason": "y"})
    assert note["ok"] is False and "paused" in note["error"]


def test_commitment_create_and_update(db, ctx):
    key = _commitment(db, "Return the spare key", due_on=TODAY)
    context = ctx()
    created = _propose(context, action="create_commitment", changes={"title": "Pay the window cleaner"})
    assert created["card"] == "New commitment: Pay the window cleaner"
    kept = _propose(context, action="update_commitment", id=str(key.id), changes={"status": "kept"})
    assert kept["card"] == "Return the spare key: Open → Kept"


def test_add_note_is_a_dated_card(db, ctx):
    boiler = _task(db, "Book the boiler service", detail="Annual service.")
    result = dispatch(
        ctx(),
        "add_note",
        {"kind": "task", "id": str(boiler.id), "note": "  Filters are 22 mm  ", "reason": "Nick said so."},
    )
    assert result["ok"] is True
    assert result["card"] == "Note on Book the boiler service: “Filters are 22 mm”"
    proposal = db.get(AgentProposal, result["proposal_id"])
    assert proposal.changes == {"note": "Filters are 22 mm", "dated": "2026-11-02"}
    assert db.get(Task, boiler.id).detail == "Annual service."


def test_add_note_refuses_repeats_and_overflow(db, ctx):
    boiler = _task(db, "Book the boiler service", detail="Annual service. Filters are 22 mm.")
    repeat = dispatch(ctx(), "add_note", {"kind": "task", "id": str(boiler.id), "note": "filters are 22 mm",
                                          "reason": "x"})
    assert repeat["ok"] is False and "already says" in repeat["error"]
    full = _task(db, "Long one", detail="x" * 3990)
    overflow = dispatch(ctx(), "add_note", {"kind": "task", "id": str(full.id), "note": "One more line",
                                            "reason": "x"})
    assert overflow["ok"] is False and "full" in overflow["error"]


def test_shopping_proposal_waits_for_apply(db, ctx):
    from uuid import UUID

    from organiser.agent.service import apply_proposal
    from organiser.models import ShoppingItem

    result = dispatch(
        ctx(),
        "propose_change",
        {"action": "create_shopping_item", "changes": {"name": "Oat milk"}, "reason": "For the week."},
    )
    assert result["ok"] is True
    assert result["card"] == "Add to shopping: Oat milk"
    assert db.scalars(select(ShoppingItem)).all() == []

    proposal, applied = apply_proposal(db, UUID(result["proposal_id"]), MONDAY_8)
    db.flush()
    rows = list(db.scalars(select(ShoppingItem)))
    assert proposal.status == "applied"
    assert [row.name for row in rows] == ["Oat milk"]
    assert rows[0].ticked is False
    assert applied["ref_type"] == "shopping"

    allergen = dispatch(
        ctx(),
        "propose_change",
        {
            "action": "create_shopping_item",
            "changes": {"name": "Bread", "allergen": "gluten"},
            "reason": "No.",
        },
    )
    assert allergen["ok"] is False
    outside = dispatch(
        ctx(),
        "propose_change",
        {"action": "create_shopping_item", "changes": {"name": "Guest soap"}, "reason": "No."},
    )
    assert outside["ok"] is False and "house log" in outside["error"]


def test_dispatch_handles_unknown_names_and_bad_json(ctx):
    context = ctx()
    assert dispatch(context, "delete_everything", "{}") == {
        "ok": False,
        "error": "There is no function called 'delete_everything'.",
    }
    assert dispatch(context, "search_items", "{not json")["error"] == "The arguments are not valid JSON."
    assert dispatch(context, "search_items", "[1, 2]")["error"] == "The arguments must be a JSON object."
    assert dispatch(context, "get_state", "")["ok"] is True
    assert dispatch(context, "get_state", None)["ok"] is True
