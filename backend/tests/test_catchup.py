"""Catch-up after a gap. Rules are fixed here; nothing calls Mistral."""

from datetime import timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from agent_fakes import london
from organiser.models import AgentRun, CatchUpItem, CatchUpPass, SystemState, Task
from organiser.services.catchup import gap_due, is_quiet


def _look(client):
    response = client.post("/catch-up/look")
    assert response.status_code == 200, response.text
    return response.json()


def _task(client, **fields):
    payload = {"title": "Put the bins out", "priority": "medium", "status": "todo"}
    payload.update(fields)
    response = client.post("/tasks", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def _commitment(client, **fields):
    payload = {"title": "Collect the dry cleaning", "status": "open"}
    payload.update(fields)
    response = client.post("/commitments", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def _at(house_clock, year, month, day, hour, minute=0):
    house_clock["now"] = london(year, month, day, hour, minute)


def _count(db, model):
    db.expire_all()
    return db.scalar(select(func.count()).select_from(model))


def _last_look(db):
    db.expire_all()
    return db.get(SystemState, 1).last_looked_at


def test_quiet_hours_and_gap_window():
    assert is_quiet(london(2026, 11, 2, 22, 0))
    assert is_quiet(london(2026, 11, 2, 5, 59))
    assert is_quiet(london(2026, 11, 2, 0, 0))
    assert not is_quiet(london(2026, 11, 2, 6, 0))
    assert not is_quiet(london(2026, 11, 2, 21, 59))

    morning = london(2026, 11, 2, 8, 0)
    assert not gap_due(morning, london(2026, 11, 2, 15, 59))
    assert gap_due(morning, london(2026, 11, 2, 16, 0))
    # Under eight hours, but the look was yesterday.
    assert gap_due(london(2026, 11, 1, 23, 30), london(2026, 11, 2, 6, 30))
    # A look during the night is the same London day as 06:30, and a short gap.
    assert not gap_due(london(2026, 11, 2, 1, 0), london(2026, 11, 2, 6, 30))


def test_first_look_records_and_shows_nothing(client, db, house_clock):
    _at(house_clock, 2026, 11, 2, 8, 0)
    _task(client, title="Put the bins out", due_on="2026-11-02")
    body = _look(client)
    assert body["items"] == []
    assert body["paused"] is False
    assert body["quiet"] is False
    assert body["house_date"] == "2026-11-02"
    assert _count(db, CatchUpPass) == 0
    assert _last_look(db) == london(2026, 11, 2, 8, 0)
    assert client.get("/agent").status_code == 200
    assert _count(db, AgentRun) == 0


def test_six_hours_does_not_open(client, db, house_clock):
    _task(client, title="Put the bins out", due_on="2026-11-02")
    _at(house_clock, 2026, 11, 2, 8, 0)
    _look(client)
    _at(house_clock, 2026, 11, 2, 14, 0)
    assert _look(client)["items"] == []
    assert _count(db, CatchUpPass) == 0
    assert _last_look(db) == london(2026, 11, 2, 14, 0)


def test_eight_hours_opens_one_shared_pass(client, db, house_clock):
    _task(client, title="Put the bins out", due_on="2026-11-02", priority="high")
    _at(house_clock, 2026, 11, 2, 8, 0)
    _look(client)
    _at(house_clock, 2026, 11, 2, 16, 0)

    body = _look(client)
    [card] = body["items"]
    assert card["rule"] == "due_today"
    assert card["label"] == "Due today"
    assert card["summary"] == "Note on Put the bins out: “Due today.”"
    assert card["reason"] == "Due today"
    assert card["status"] == "pending"
    assert _count(db, CatchUpPass) == 1

    again = _look(client)
    assert [item["id"] for item in again["items"]] == [card["id"]]
    assert _count(db, CatchUpPass) == 1
    assert _count(db, CatchUpItem) == 1


def test_eight_hours_that_lands_in_quiet_hours_waits(client, db, house_clock):
    _task(client, title="Put the bins out", due_on="2026-11-03")
    _at(house_clock, 2026, 11, 2, 14, 0)
    _look(client)
    _at(house_clock, 2026, 11, 2, 22, 0)
    quiet = _look(client)
    assert quiet["quiet"] is True
    assert quiet["items"] == []
    assert _count(db, CatchUpPass) == 0
    assert _last_look(db) == london(2026, 11, 2, 14, 0)

    _at(house_clock, 2026, 11, 3, 8, 0)
    [card] = _look(client)["items"]
    assert card["rule"] == "due_today"
    assert card["summary"] == "Note on Put the bins out: “Due today.”"


def test_overnight_under_eight_hours_opens_once(client, db, house_clock):
    _task(client, title="Replace the hallway bulb", due_on="2026-11-01", priority="medium", status="doing")
    _at(house_clock, 2026, 11, 1, 21, 0)
    _look(client)

    _at(house_clock, 2026, 11, 1, 23, 30)
    quiet = _look(client)
    assert quiet["quiet"] is True
    assert quiet["items"] == []
    assert _last_look(db) == london(2026, 11, 1, 23, 30)

    _at(house_clock, 2026, 11, 2, 6, 30)
    body = _look(client)
    [card] = body["items"]
    assert card["rule"] == "overdue"
    assert card["reason"] == "1 day overdue"
    assert card["summary"] == "Note on Replace the hallway bulb: “1 day overdue.”"
    assert _count(db, CatchUpPass) == 1


def test_quiet_look_does_not_spend_a_due_gap(client, db, house_clock):
    _task(client, title="Put the bins out", due_on="2026-11-02")
    _at(house_clock, 2026, 11, 1, 12, 0)
    _look(client)

    _at(house_clock, 2026, 11, 2, 5, 30)
    body = _look(client)
    assert body["quiet"] is True
    assert body["items"] == []
    assert _count(db, CatchUpPass) == 0
    assert _last_look(db) == london(2026, 11, 1, 12, 0)

    _at(house_clock, 2026, 11, 2, 6, 0)
    opened = _look(client)
    assert len(opened["items"]) == 1
    assert _count(db, CatchUpPass) == 1


def test_get_does_not_record_a_look_or_open_a_pass(client, db, house_clock):
    _task(client, title="Put the bins out", due_on="2026-11-02")
    _at(house_clock, 2026, 11, 2, 8, 0)
    _look(client)
    _at(house_clock, 2026, 11, 2, 17, 0)

    response = client.get("/catch-up")
    assert response.status_code == 200
    assert response.json()["items"] == []
    assert _count(db, CatchUpPass) == 0
    assert _last_look(db) == london(2026, 11, 2, 8, 0)

    assert len(_look(client)["items"]) == 1


def test_pause_blocks_the_gap_and_both_taps(client, db, house_clock):
    task = _task(client, title="Put the bins out", due_on="2026-11-01", detail="Green bin.")
    _at(house_clock, 2026, 11, 2, 8, 0)
    _look(client)
    missing = client.post(f"/catch-up/items/{task['id']}/apply")
    assert missing.status_code == 404
    assert missing.json()["detail"] == "No such catch-up."

    _at(house_clock, 2026, 11, 2, 18, 0)
    assert client.post("/system/pause").status_code == 200

    paused = _look(client)
    assert paused["paused"] is True
    assert paused["items"] == []
    assert _count(db, CatchUpPass) == 0
    assert _last_look(db) == london(2026, 11, 2, 8, 0)
    assert client.post(f"/catch-up/items/{task['id']}/apply").status_code == 409

    assert client.post("/system/unpause").status_code == 200
    [card] = _look(client)["items"]
    assert client.post("/system/pause").status_code == 200

    refused = client.post(f"/catch-up/items/{card['id']}/apply")
    assert refused.status_code == 409
    assert refused.json()["detail"] == "The house is paused. Nothing was changed."
    dismissed = client.post(f"/catch-up/items/{card['id']}/dismiss")
    assert dismissed.status_code == 409
    assert client.get(f"/tasks/{task['id']}").json()["detail"] == "Green bin."

    assert client.post("/system/unpause").status_code == 200
    # The gap was not spent while paused, and the card is still waiting.
    assert [item["id"] for item in _look(client)["items"]] == [card["id"]]


def test_cards_are_capped_and_ranked(client, house_clock):
    _task(client, title="Zebra", due_on="2026-10-28", priority="high")
    _task(client, title="Apple", due_on="2026-10-28", priority="low")
    _task(client, title="Mango", due_on="2026-11-01", priority="high")
    _task(client, title="Bins", due_on="2026-11-02", priority="high")
    _task(client, title="Plants", due_on="2026-11-02", priority="low")
    _commitment(client, title="Spare key", due_on="2026-11-03")
    _at(house_clock, 2026, 11, 2, 8, 0)
    _look(client)
    _at(house_clock, 2026, 11, 2, 17, 0)

    body = _look(client)
    assert [item["rule"] for item in body["items"]] == ["overdue", "overdue", "overdue", "due_today"]
    assert [item["summary"] for item in body["items"]] == [
        "Note on Zebra: “5 days overdue.”",
        "Note on Apple: “5 days overdue.”",
        "Note on Mango: “1 day overdue.”",
        "Note on Bins: “Due today.”",
    ]
    assert "Plants" not in " ".join(item["summary"] for item in body["items"])
    assert "Spare key" not in " ".join(item["summary"] for item in body["items"])


def test_stalled_commitment_and_brief_fill_when_nothing_is_more_pressing(client, db, house_clock):
    stalled = _task(client, title="Mend the stair rod", status="doing", due_on="2026-11-10")
    recent = _task(client, title="Oil the hinge", status="doing", due_on="2026-11-10")
    brief = _task(client, title="Label the fuse box", due_on=None, priority="low")
    _task(client, title="Done already", status="done", due_on="2026-11-01")
    tomorrow = _commitment(client, title="Return the spare key", due_on="2026-11-03")
    _commitment(client, title="Library books", status="kept", due_on="2026-11-02")
    later = _commitment(client, title="Service the mower", due_on=None)

    _at(house_clock, 2026, 11, 2, 8, 0)
    db.get(Task, stalled["id"]).updated_at = london(2026, 10, 30, 8, 0)
    db.get(Task, recent["id"]).updated_at = london(2026, 10, 31, 8, 0)
    db.commit()
    _look(client)
    _at(house_clock, 2026, 11, 2, 17, 0)

    body = _look(client)
    by_title = {item["summary"]: item for item in body["items"]}
    assert len(body["items"]) == 4
    assert by_title["Note on Mend the stair rod: “No update for 3 days.”"]["rule"] == "stalled"
    assert by_title["Note on Mend the stair rod: “No update for 3 days.”"]["reason"] == (
        "In progress, no update for 3 days"
    )
    assert by_title["Note on Return the spare key: “Due tomorrow.”"]["rule"] == "commitment_due"
    assert by_title["Note on Return the spare key: “Due tomorrow.”"]["ref_id"] == tomorrow["id"]
    assert by_title["Note on Label the fuse box: “Still on the brief, with no date.”"]["rule"] == "brief"
    assert by_title["Note on Service the mower: “Still open on the brief.”"]["rule"] == "brief"
    assert by_title["Note on Service the mower: “Still open on the brief.”"]["ref_id"] == later["id"]
    assert all(item["ref_id"] != recent["id"] for item in body["items"])
    assert all(item["ref_id"] != brief["id"] or item["rule"] == "brief" for item in body["items"])
    assert "Oil the hinge" not in " ".join(item["summary"] for item in body["items"])
    assert "Done already" not in " ".join(item["summary"] for item in body["items"])
    assert "Library books" not in " ".join(item["summary"] for item in body["items"])


def test_a_task_due_today_is_not_also_called_stalled(client, db, house_clock):
    task = _task(client, title="Replace the hallway bulb", status="doing", due_on="2026-11-02")
    _at(house_clock, 2026, 11, 2, 8, 0)
    db.get(Task, task["id"]).updated_at = london(2026, 10, 28, 8, 0)
    db.commit()
    _look(client)
    _at(house_clock, 2026, 11, 2, 17, 0)
    [card] = _look(client)["items"]
    assert card["rule"] == "due_today"
    assert card["reason"] == "Due today"


def test_apply_adds_one_note_and_leaves_the_rest_of_the_log(client, db, house_clock):
    task = _task(client, title="Put the bins out", due_on="2026-11-01", detail="Green bin.", priority="high")
    request = client.post(
        "/action-requests",
        json={"title": "Leave a note for the plumber", "mode": "execute", "owner": "Nick"},
    )
    assert request.status_code == 201
    _at(house_clock, 2026, 11, 2, 8, 0)
    _look(client)
    _at(house_clock, 2026, 11, 2, 17, 0)
    [card] = _look(client)["items"]

    response = client.post(f"/catch-up/items/{card['id']}/apply")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["item"]["status"] == "applied"
    assert body["applied"]["ref_type"] == "task"
    assert body["applied"]["ref_id"] == task["id"]
    assert body["applied"]["summary"] == card["summary"]

    saved = client.get(f"/tasks/{task['id']}").json()
    assert saved["detail"] == "Green bin.\n2 Nov: 1 day overdue."
    assert saved["status"] == "todo"
    assert saved["due_on"] == "2026-11-01"
    assert saved["owner"] == "Nick"
    assert saved["priority"] == "high"

    again = client.post(f"/catch-up/items/{card['id']}/apply")
    assert again.status_code == 409
    assert again.json()["detail"] == "This has already been decided."

    events = client.get("/events").json()["items"]
    assert len(events) == 1
    assert events[0]["kind"] == "task"
    assert events[0]["title"].startswith("Catch-up:")
    assert "Nothing outside the house log was changed." in events[0]["body"]

    pending = client.get("/action-requests").json()["items"]
    assert pending[0]["status"] == "pending"
    assert pending[0]["effect_applied"] is False
    assert _count(db, AgentRun) == 0

    # Apply does not rest the item: the next gap can mention it again.
    _at(house_clock, 2026, 11, 3, 8, 0)
    follow = _look(client)
    assert [item["ref_id"] for item in follow["items"]] == [task["id"]]
    assert _count(db, CatchUpPass) == 2


def test_apply_on_a_commitment_and_a_changed_row_is_refused(client, house_clock):
    commitment = _commitment(client, title="Return the spare key", due_on="2026-11-03", detail="They lent it.")
    _at(house_clock, 2026, 11, 2, 8, 0)
    _look(client)
    _at(house_clock, 2026, 11, 2, 17, 0)
    [card] = _look(client)["items"]
    assert card["ref_type"] == "commitment"

    edited = client.patch(f"/commitments/{commitment['id']}", json={"detail": "Handed back."})
    assert edited.status_code == 200
    refused = client.post(f"/catch-up/items/{card['id']}/apply")
    assert refused.status_code == 409
    assert refused.json()["detail"] == "The item changed since this was prepared. Nothing was applied."
    assert client.get(f"/commitments/{commitment['id']}").json()["detail"] == "Handed back."
    assert _look(client)["items"] == []

    # A fresh gap prepares a new card from the row as it stands.
    _at(house_clock, 2026, 11, 3, 8, 0)
    [fresh] = _look(client)["items"]
    applied = client.post(f"/catch-up/items/{fresh['id']}/apply")
    assert applied.status_code == 200, applied.text
    assert client.get(f"/commitments/{commitment['id']}").json()["detail"] == (
        "Handed back.\n3 Nov: Due today."
    )


def test_dismiss_rests_the_item_for_72_hours(client, db, house_clock):
    zebra = _task(client, title="Zebra", due_on="2026-10-28", priority="high", detail="Leave it.")
    apple = _task(client, title="Apple", due_on="2026-10-28", priority="high", detail="Leave it.")
    _at(house_clock, 2026, 11, 2, 8, 0)
    _look(client)
    _at(house_clock, 2026, 11, 2, 16, 0)
    cards = _look(client)["items"]
    assert [card["ref_id"] for card in cards] == [apple["id"], zebra["id"]]

    dismissed = client.post(f"/catch-up/items/{cards[1]['id']}/dismiss")
    assert dismissed.status_code == 200
    assert dismissed.json()["status"] == "dismissed"
    assert client.get(f"/tasks/{zebra['id']}").json()["detail"] == "Leave it."
    other = client.post(f"/catch-up/items/{cards[0]['id']}/dismiss")
    assert other.status_code == 200
    repeat = client.post(f"/catch-up/items/{cards[1]['id']}/dismiss")
    assert repeat.status_code == 409

    bulb = _task(client, title="New bulb", due_on="2026-10-28", priority="medium")
    _at(house_clock, 2026, 11, 3, 8, 0)
    follow = _look(client)
    assert [item["ref_id"] for item in follow["items"]] == [bulb["id"]]
    assert client.post(f"/catch-up/items/{follow['items'][0]['id']}/dismiss").status_code == 200

    # Still inside 72 hours of every Not now.
    _at(house_clock, 2026, 11, 5, 7, 0)
    assert _look(client)["items"] == []

    _at(house_clock, 2026, 11, 6, 10, 0)
    titles = [item["summary"] for item in _look(client)["items"]]
    assert titles == [
        "Note on Apple: “9 days overdue.”",
        "Note on Zebra: “9 days overdue.”",
        "Note on New bulb: “9 days overdue.”",
    ]
    assert _count(db, CatchUpPass) == 3


def test_pending_cards_hide_in_quiet_hours_and_stay_one_pass(client, db, house_clock):
    _task(client, title="Put the bins out", due_on="2026-11-02")
    _at(house_clock, 2026, 11, 2, 8, 0)
    _look(client)
    _at(house_clock, 2026, 11, 2, 16, 0)
    first = _look(client)
    assert len(first["items"]) == 1

    _at(house_clock, 2026, 11, 2, 22, 30)
    hidden = _look(client)
    assert hidden["items"] == []
    assert hidden["quiet"] is True
    reading = client.get("/catch-up")
    assert reading.json()["items"] == []

    _at(house_clock, 2026, 11, 3, 8, 0)
    again = _look(client)
    assert [item["id"] for item in again["items"]] == [item["id"] for item in first["items"]]
    assert _count(db, CatchUpPass) == 1


def test_one_window_key_and_only_a_note(db):
    when = london(2026, 11, 2, 8, 0)
    db.add(CatchUpPass(window_key="gap:once", opened_at=when, from_looked_at=when - timedelta(hours=9)))
    db.commit()
    db.add(CatchUpPass(window_key="gap:once", opened_at=when, from_looked_at=when))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()

    pass_row = db.scalars(select(CatchUpPass)).one()
    db.add(
        CatchUpItem(
            pass_id=pass_row.id,
            position=0,
            rule="chat",
            label="Overdue",
            action="add_note",
            ref_type="task",
            ref_id=pass_row.id,
            changes={"note": "no"},
            summary="no",
            reason="no",
            ref_updated_at=when,
            status="pending",
            created_at=when,
        )
    )
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_catchup_rows_reject_anything_but_a_note(db):
    when = london(2026, 11, 2, 8, 0)
    pass_row = CatchUpPass(window_key="gap:note", opened_at=when, from_looked_at=when - timedelta(hours=9))
    db.add(pass_row)
    db.commit()
    db.add(
        CatchUpItem(
            pass_id=pass_row.id,
            position=0,
            rule="overdue",
            label="Overdue",
            action="create_task",
            ref_type="task",
            ref_id=pass_row.id,
            changes={"note": "no"},
            summary="no",
            reason="no",
            ref_updated_at=when,
            status="pending",
            created_at=when,
        )
    )
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
