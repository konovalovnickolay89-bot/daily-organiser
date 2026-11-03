"""Activity poll and propose-only ingest. Neither path calls Mistral."""

import re

import pytest
from sqlalchemy import func, inspect, select

from agent_fakes import london, say
from organiser.db import ensure_ingest_proposals
from organiser.models import AgentRun, Task

_OFFSET = re.compile(r"T.*(?:Z|[+-]\d{2}:\d{2})$")


def _proposal(client, **fields):
    payload = {
        "title": "Buy oat milk",
        "due_on": "2026-11-06",
        "reason": "The note said it was low.",
        "source": "curator",
    }
    payload.update(fields)
    if "due_on" in payload and payload["due_on"] is None:
        del payload["due_on"]
    return client.post("/agent/proposals", json=payload)


def test_ingest_column_shape_survives_a_second_ensure(database):
    ensure_ingest_proposals()
    ensure_ingest_proposals()
    columns = {column["name"]: column for column in inspect(database).get_columns("agent_proposals")}
    assert columns["run_id"]["nullable"] is True


def test_activity_lists_recent_lines_newest_first(client):
    assert client.get("/agent/activity").json() == {"items": []}
    assert client.post(
        "/events",
        json={"kind": "note", "title": "Milk is low", "recorded_at": "2026-11-01T10:00:00+00:00"},
    ).status_code == 201
    assert client.post(
        "/events",
        json={"kind": "system", "title": "House paused", "recorded_at": "2026-11-02T09:00:00+00:00"},
    ).status_code == 201
    assert client.post(
        "/events",
        json={
            "kind": "task",
            "title": "Applied: New task: Buy oat milk",
            "recorded_at": "2026-11-02T11:00:00+00:00",
        },
    ).status_code == 201
    assert client.post(
        "/events",
        json={"kind": "task", "title": "Catch-up: Put the bins out", "recorded_at": "2026-11-02T08:00:00+00:00"},
    ).status_code == 201

    body = client.get("/agent/activity").json()
    assert [(item["type"], item["text"]) for item in body["items"]] == [
        ("apply", "Applied: New task: Buy oat milk"),
        ("pause", "House paused"),
        ("catchup", "Catch-up: Put the bins out"),
        ("note", "Milk is low"),
    ]
    for item in body["items"]:
        assert item["id"]
        assert _OFFSET.search(item["at"])

    # 10:00 UTC on a summer day is 11:00 in Europe/London.
    assert client.post(
        "/events",
        json={"kind": "system", "title": "House resumed", "recorded_at": "2026-08-01T10:00:00+00:00"},
    ).status_code == 201
    summer = next(item for item in client.get("/agent/activity").json()["items"] if item["text"] == "House resumed")
    assert summer["type"] == "resume"
    assert summer["at"] == "2026-08-01T11:00:00+01:00"

    later = client.get("/agent/activity", params={"since": "2026-11-02T09:00:00+00:00"}).json()
    assert [item["type"] for item in later["items"]] == ["apply"]
    assert len(client.get("/agent/activity", params={"limit": 1}).json()["items"]) == 1


def test_activity_follows_add_pause_and_catchup(client, house_clock):
    house_clock["now"] = london(2026, 11, 2, 8, 0)
    assert client.post(
        "/tasks",
        json={"title": "Put the bins out", "due_on": "2026-11-01", "priority": "high"},
    ).status_code == 201
    assert client.post("/commitments", json={"title": "Collect the dry cleaning"}).status_code == 201
    assert client.post("/catch-up/look").json()["items"] == []
    house_clock["now"] = london(2026, 11, 2, 17, 0)
    cards = client.post("/catch-up/look").json()["items"]
    assert cards
    assert client.post(f"/catch-up/items/{cards[0]['id']}/apply").status_code == 200
    assert client.post("/system/pause").status_code == 200

    items = client.get("/agent/activity").json()["items"]
    assert items[0]["type"] == "pause"
    assert items[0]["text"] == "House paused"
    kinds = {item["type"] for item in items}
    assert {"add", "catchup", "pause"} <= kinds
    assert any(item["text"] == "Added: Put the bins out" for item in items)
    assert any(item["text"] == "Added: Collect the dry cleaning" for item in items)
    assert any(item["text"].startswith("Catch-up:") for item in items)


def test_activity_never_calls_mistral(client, house_clock, mistral):
    fake = mistral()
    assert client.get("/agent/activity").status_code == 200
    assert client.post("/agent/proposals", json={"title": "Buy oat milk"}).status_code == 201
    assert fake.calls == []


def test_post_proposal_is_a_pending_card_and_not_a_task(client, db, house_clock):
    response = client.post(
        "/agent/proposals",
        json={
            "title": "  Buy oat milk  ",
            "due_on": "2026-11-06",
            "reason": "  The note said it was low.  ",
            "source": "  curator  ",
        },
    )
    assert response.status_code == 201, response.text
    card = response.json()
    assert card["status"] == "pending"
    assert card["origin"] == "ingest"
    assert card["action"] == "create_task"
    assert card["rule"] == "feed"
    assert card["label"] == "curator"
    assert card["summary"] == "New task: Buy oat milk · due Fri 6 Nov"
    assert card["reason"] == "The note said it was low."
    assert card["ref_id"] is None
    assert card["applied_ref_id"] is None

    assert client.get("/tasks").json()["items"] == []
    assert client.get("/commitments").json()["items"] == []
    state = client.get("/agent").json()
    assert state["enabled"] is False
    assert [item["id"] for item in state["proposals"]] == [card["id"]]
    assert db.scalar(select(func.count()).select_from(AgentRun)) == 0
    assert db.scalar(select(func.count()).select_from(Task)) == 0

    [line] = client.get("/agent/activity").json()["items"]
    assert line["type"] == "proposal"
    assert line["text"] == "Proposed: New task: Buy oat milk · due Fri 6 Nov"


def test_apply_on_an_ingested_card_creates_the_task(client, house_clock):
    card = _proposal(client).json()
    applied = client.post(f"/agent/proposals/{card['id']}/apply")
    assert applied.status_code == 200, applied.text
    body = applied.json()
    assert body["proposal"]["status"] == "applied"
    assert body["applied"]["ref_type"] == "task"
    assert body["applied"]["summary"] == card["summary"]

    [task] = client.get("/tasks").json()["items"]
    assert task["id"] == body["applied"]["ref_id"]
    assert (task["title"], task["due_on"], task["status"], task["owner"], task["priority"]) == (
        "Buy oat milk",
        "2026-11-06",
        "todo",
        "Nick",
        "medium",
    )
    assert client.get("/agent").json()["proposals"] == []
    types = [item["type"] for item in client.get("/agent/activity").json()["items"]]
    assert types[0] == "apply"
    assert "proposal" in types


def test_not_now_on_an_ingested_card_creates_nothing(client, house_clock):
    card = _proposal(client).json()
    dismissed = client.post(f"/agent/proposals/{card['id']}/dismiss")
    assert dismissed.status_code == 200
    assert dismissed.json()["status"] == "dismissed"
    assert client.post(f"/agent/proposals/{card['id']}/apply").status_code == 409
    assert client.get("/tasks").json()["items"] == []
    assert client.get("/agent").json()["proposals"] == []


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"title": "   "},
        {"title": ""},
        {"title": "Buy oat milk", "due_on": "Friday"},
        {"title": "Buy oat milk", "due_on": "2026-11-01"},
        {"title": "Book a hotel room"},
        {"title": "Buy oat milk", "reason": "Ask the employer"},
        {"title": "x" * 201},
    ],
)
def test_invalid_proposals_are_rejected(client, house_clock, payload):
    response = client.post("/agent/proposals", json=payload)
    assert response.status_code == 422, response.text
    assert client.get("/tasks").json()["items"] == []
    assert client.get("/agent").json()["proposals"] == []
    assert client.get("/events").json()["items"] == []


def test_duplicates_are_refused_and_a_done_task_does_not_block(client, house_clock):
    assert client.post("/tasks", json={"title": "Put the bins out"}).status_code == 201
    same = _proposal(client, title="Put the bins out")
    assert same.status_code == 409
    assert "open task" in same.json()["detail"]

    created = client.post("/tasks", json={"title": "Water the houseplants", "status": "done"})
    assert created.status_code == 201
    done = _proposal(client, title="Water the houseplants", due_on=None)
    assert done.status_code == 201, done.text

    assert client.post("/commitments", json={"title": "Collect the dry cleaning"}).status_code == 201
    commitment = _proposal(client, title="Collect the dry cleaning")
    assert commitment.status_code == 409
    assert "open commitment" in commitment.json()["detail"]

    assert _proposal(client, title="Buy oat milk").status_code == 201
    again = _proposal(client, title="buy oat milk")
    assert again.status_code == 409
    assert "already waiting" in again.json()["detail"]

    titles = [item["title"] for item in client.get("/tasks").json()["items"]]
    assert titles == ["Put the bins out", "Water the houseplants"]
    assert len(client.get("/agent").json()["proposals"]) == 2


def test_pending_cap_stops_a_flood(client, house_clock, monkeypatch):
    monkeypatch.setattr("organiser.agent.ingest.MAX_PENDING_PROPOSALS", 2)
    assert _proposal(client, title="One").status_code == 201
    assert _proposal(client, title="Two").status_code == 201
    full = _proposal(client, title="Three")
    assert full.status_code == 409
    assert full.json()["detail"] == "The proposal list is full. Apply or dismiss a card first."
    assert len(client.get("/agent").json()["proposals"]) == 2
    assert client.get("/tasks").json()["items"] == []


def test_paused_house_stores_nothing(client, house_clock):
    assert client.post("/system/pause").status_code == 200
    response = _proposal(client)
    assert response.status_code == 409
    assert response.json()["detail"] == "The house is paused. Nothing was proposed."
    assert client.get("/agent").json()["proposals"] == []
    assert client.get("/tasks").json()["items"] == []
    activity = client.get("/agent/activity").json()["items"]
    assert activity[0]["type"] == "pause"
    assert activity[0]["text"] == "House paused"


def test_add_writes_an_activity_line_and_still_only_proposes(client, house_clock, mistral):
    mistral([say("Nothing to add.")])
    assert client.post("/agent/feed", json={"text": "need more oat milk"}).status_code == 200
    assert client.get("/tasks").json()["items"] == []
    assert client.get("/agent").json()["proposals"] == []
    item = client.get("/agent/activity").json()["items"][0]
    assert item["type"] == "add"
    assert item["text"] == "Added: need more oat milk"


def test_an_add_outside_the_house_is_not_stored_as_activity(client, house_clock, mistral):
    mistral([say("Not for the house log.")])
    assert client.post("/agent/feed", json={"text": "book a hotel for a guest"}).status_code == 200
    assert client.get("/agent/activity").json()["items"] == []
    assert client.get("/tasks").json()["items"] == []
