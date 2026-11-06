"""The assistant through the API, with a scripted Mistral and a frozen house clock."""

import json
from datetime import timedelta

from sqlalchemy import select

from agent_fakes import call, london, say
from organiser.agent.mistral import MistralUnavailable
from organiser.config import get_settings
from organiser.models import AgentRun, Task

FILTERS = {
    "action": "create_task",
    "changes": {"title": "Buy boiler filters", "due_on": "2026-11-06"},
    "reason": "Needed before Friday's service.",
}


def _feed(client, text="need filters for the boiler before Friday"):
    return client.post("/agent/feed", json={"text": text})


def _state(client):
    return client.get("/agent").json()


def _add_task(client, **fields):
    return client.post("/tasks", json={"title": "Book the boiler service", **fields}).json()


def _set_updated_at(db, task_id, when):
    db.get(Task, task_id).updated_at = when
    db.commit()


# --- switched off -----------------------------------------------------------


def test_off_without_a_key_and_nothing_is_sent(client, house_clock):
    state = _state(client)
    assert state["enabled"] is False
    assert state["reachable"] is False
    assert state["due"] is None
    assert state["proposals"] == []
    response = _feed(client)
    assert response.status_code == 503
    assert response.json()["detail"] == "The assistant is off. Nothing was sent."


def test_get_never_calls_mistral(client, house_clock, mistral):
    fake = mistral()
    for _ in range(3):
        assert client.get("/agent").status_code == 200
    assert fake.calls == []


# --- the box on the screen --------------------------------------------------


def test_feed_turns_text_into_one_card(client, db, house_clock, mistral):
    fake = mistral(
        [call("get_state")],
        [call("search_items", {"text": "filter"})],
        [call("propose_change", FILTERS)],
        [say("Added 1 proposal: boiler filters (Fri).\nNothing else.\nThird line is dropped.")],
    )
    response = _feed(client)
    assert response.status_code == 200
    body = response.json()
    assert body["trigger"] == "feed"
    assert body["reply"] == "Added 1 proposal: boiler filters (Fri).\nNothing else."
    assert body["searched"] is False
    [card] = body["proposals"]
    assert card["summary"] == "New task: Buy boiler filters · due Fri 6 Nov"
    assert card["label"] == "From your note"
    assert card["reason"] == "Needed before Friday's service."
    assert card["status"] == "pending"

    # What went to Mistral: the agent id, a brief with the house time, then function results.
    kind, agent_id, packet = fake.calls[0]
    assert (kind, agent_id) == ("start", "ag_test")
    assert "Trigger: feed" in packet
    assert "House time: Monday 2 November 2026, 08:00 (Europe/London)" in packet
    assert "Proposal limit: 3" in packet
    assert "need filters for the boiler before Friday" in packet
    results = fake.results()
    assert results[0]["house_date"] == "2026-11-02"
    assert results[1] == {"ok": True, "count": 0, "items": []}
    assert results[2]["ok"] is True
    assert fake.deleted == ["conv_test"]

    # Nothing was changed: the card waits for a tap.
    assert client.get("/tasks").json()["items"] == []
    state = _state(client)
    assert [p["id"] for p in state["proposals"]] == [card["id"]]
    assert state["last_reply"]["text"] == body["reply"]
    assert state["runs_left_today"] == 11
    assert state["reachable"] is True

    run = db.scalars(select(AgentRun)).one()
    assert run.status == "done"
    assert run.input_text == "need filters for the boiler before Friday"


def test_refusals_go_back_to_the_model_not_to_the_screen(client, house_clock, mistral):
    fake = mistral(
        [call("propose_change", {**FILTERS, "changes": {"title": "Buy boiler filters", "due_on": "next week"}})],
        [call("propose_change", FILTERS)],
        [say("Added 1 proposal.")],
    )
    body = _feed(client).json()
    assert len(body["proposals"]) == 1
    first, second = fake.results()
    assert first["ok"] is False and "due_on" in first["error"]
    assert second["ok"] is True


def test_web_search_is_noted(client, house_clock, mistral):
    mistral([{"object": "entry", "type": "tool.execution", "name": "web_search"}, say("The tip opens at 8.")])
    body = _feed(client, "when does the tip open on saturday").json()
    assert body["searched"] is True
    assert body["reply"] == "The tip opens at 8."
    assert body["proposals"] == []


def test_paused_house_sends_nothing(client, house_clock, mistral):
    fake = mistral()
    client.post("/system/pause")
    response = _feed(client)
    assert response.status_code == 409
    assert response.json()["detail"] == "The house is paused. Nothing was sent to the assistant."
    assert fake.calls == []
    state = _state(client)
    assert state["paused"] is True
    assert state["due"] is None


def test_daily_run_cap(client, house_clock, mistral, monkeypatch):
    monkeypatch.setenv("AGENT_RUNS_PER_DAY", "1")
    get_settings.cache_clear()
    mistral([say("Nothing to add.")])
    assert _feed(client).status_code == 200
    capped = _feed(client)
    assert capped.status_code == 429
    assert capped.json()["detail"] == "The assistant has used its runs for today. Nothing was sent."
    assert _state(client)["runs_left_today"] == 0

    house_clock["now"] = london(2026, 11, 3, 0, 5)
    mistral([say("Nothing to add.")])
    assert _feed(client).status_code == 200


def test_a_run_that_does_not_finish_leaves_nothing(client, db, house_clock, mistral):
    mistral(
        [call("propose_change", FILTERS)],
        *[[call("get_state", call_id=f"call_{n}")] for n in range(6)],
    )
    response = _feed(client)
    assert response.status_code == 424
    assert response.json()["detail"] == "The assistant did not finish. Nothing was changed."
    assert _state(client)["proposals"] == []
    run = db.scalars(select(AgentRun)).one()
    assert run.status == "failed"
    assert run.error == "The assistant did not finish."


def test_mistral_down_changes_nothing(client, db, house_clock, mistral):
    mistral([call("propose_change", FILTERS)], MistralUnavailable("Mistral could not be reached."))
    response = _feed(client)
    assert response.status_code == 424
    assert response.json()["detail"] == "The assistant could not be reached. Nothing was changed."
    assert _state(client)["proposals"] == []
    assert _state(client)["reachable"] is False
    assert db.scalars(select(AgentRun)).one().status == "failed"


def _events(body: str) -> list[tuple[str, dict]]:
    found = []
    for block in body.split("\n\n"):
        if not block.strip():
            continue
        event = "message"
        data = ""
        for line in block.splitlines():
            if line.startswith("event:"):
                event = line.split(":", 1)[1].strip()
            elif line.startswith("data:"):
                data += line.split(":", 1)[1].strip()
        found.append((event, json.loads(data)))
    return found


def test_feed_stream_reports_steps_then_the_card(client, house_clock, mistral):
    mistral(
        [call("get_state")],
        [call("search_items", {"text": "filter"})],
        [call("propose_change", FILTERS)],
        [say("Added 1 proposal.")],
    )
    response = client.post(
        "/agent/feed",
        json={"text": "need filters for the boiler before Friday"},
        headers={"Accept": "text/event-stream"},
    )
    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]
    events = _events(response.text)
    steps = [data["step"] for kind, data in events if kind == "step"]
    assert steps[0] == "received"
    assert "calling" in steps
    assert "reading" in steps
    assert steps.index("received") < steps.index("calling") < steps.index("reading")
    done = [data for kind, data in events if kind == "done"]
    assert len(done) == 1
    assert done[0]["reply"] == "Added 1 proposal."
    assert done[0]["proposals"][0]["summary"] == "New task: Buy boiler filters · due Fri 6 Nov"
    assert [proposal["id"] for proposal in _state(client)["proposals"]] == [done[0]["proposals"][0]["id"]]


def test_feed_stream_failure_stays_in_the_page(client, db, house_clock, mistral):
    mistral(
        [call("propose_change", FILTERS)],
        *[[call("get_state", call_id=f"call_{n}")] for n in range(6)],
    )
    response = client.post(
        "/agent/feed",
        json={"text": "need filters for the boiler before Friday"},
        headers={"Accept": "text/event-stream"},
    )
    assert response.status_code == 200
    events = _events(response.text)
    errors = [data for kind, data in events if kind == "error"]
    assert errors == [{"detail": "The assistant did not finish. Nothing was changed."}]
    assert not any(kind == "done" for kind, _ in events)
    assert _state(client)["proposals"] == []
    assert db.scalars(select(AgentRun)).one().status == "failed"


TRIP = {
    "action": "create_task",
    "changes": {"title": "Train to work", "due_on": "2026-11-03"},
    "reason": "Leave the house at 7.",
}
JOURNEY = {
    "action": "create_task",
    "changes": {
        "title": "Check journey tomorrow",
        "detail": "Journey source is not connected. Nothing live was checked.",
        "due_on": "2026-11-03",
    },
    "reason": "Journey source is not connected.",
}


def test_a_commute_asks_for_the_trip_and_a_journey_check(client, house_clock, mistral):
    fake = mistral(
        [call("get_state")],
        [call("search_items", {"text": "work"})],
        [call("propose_change", TRIP), call("propose_change", JOURNEY)],
        [say("Added 2 proposals.")],
    )
    body = _feed(client, "Train to work tomorrow, leave at 7").json()
    packet = fake.calls[0][2]
    assert "Journey:" in packet
    assert "Do not invent disruptions" in packet
    summaries = [proposal["summary"] for proposal in body["proposals"]]
    assert "New task: Train to work · due Tue 3 Nov" in summaries
    assert "New task: Check journey tomorrow · due Tue 3 Nov" in summaries
    assert body["proposals"][1]["reason"] == "Journey source is not connected."
    assert client.get("/tasks").json()["items"] == []


def test_a_commute_outside_the_house_does_not_ask_for_a_journey_check(client, house_clock, mistral):
    fake = mistral([say("Not for the house log.")])
    body = _feed(client, "commute with a guest tomorrow").json()
    assert "Journey:" not in fake.calls[0][2]
    assert body["proposals"] == []


def test_feed_text_is_checked(client, house_clock, mistral):
    mistral()
    assert client.post("/agent/feed", json={"text": "   "}).status_code == 422
    assert client.post("/agent/feed", json={"text": "x" * 1001}).status_code == 422


# --- Apply and Not now ------------------------------------------------------


def test_apply_creates_the_task_and_logs_one_line(client, house_clock, mistral):
    mistral([call("propose_change", FILTERS)], [say("Added 1 proposal.")])
    card = _feed(client).json()["proposals"][0]

    applied = client.post(f"/agent/proposals/{card['id']}/apply")
    assert applied.status_code == 200
    body = applied.json()
    assert body["proposal"]["status"] == "applied"
    assert body["applied"]["ref_type"] == "task"

    [task] = client.get("/tasks").json()["items"]
    assert task["id"] == body["applied"]["ref_id"]
    assert (task["title"], task["due_on"], task["status"], task["owner"]) == (
        "Buy boiler filters",
        "2026-11-06",
        "todo",
        "Nick",
    )
    events = client.get("/events?kind=task").json()["items"]
    assert [event["title"] for event in events] == ["Applied: New task: Buy boiler filters · due Fri 6 Nov"]
    assert "Nothing outside the house log was changed." in events[0]["body"]

    again = client.post(f"/agent/proposals/{card['id']}/apply")
    assert again.status_code == 409
    assert again.json()["detail"] == "This has already been decided."
    assert _state(client)["proposals"] == []


def test_apply_edits_exactly_the_named_fields(client, house_clock, mistral):
    task = _add_task(client, due_on="2026-11-04", detail="Annual service.")
    mistral(
        [call("propose_change", {"action": "update_task", "id": task["id"], "changes": {"due_on": "2026-11-09"},
                                 "reason": "Friday is full."})],
        [say("Moved 1 date.")],
    )
    card = _feed(client, "move the boiler booking to next week").json()["proposals"][0]
    assert card["summary"] == "Book the boiler service: due Wed 4 Nov → Mon 9 Nov"
    assert client.post(f"/agent/proposals/{card['id']}/apply").status_code == 200
    after = client.get(f"/tasks/{task['id']}").json()
    assert after["due_on"] == "2026-11-09"
    assert (after["title"], after["detail"], after["status"], after["priority"]) == (
        "Book the boiler service",
        "Annual service.",
        "todo",
        "medium",
    )


def test_apply_after_an_edit_is_refused_as_stale(client, house_clock, mistral):
    task = _add_task(client, due_on="2026-11-04")
    mistral(
        [call("propose_change", {"action": "update_task", "id": task["id"], "changes": {"status": "done"},
                                 "reason": "Looks finished."})],
        [say("1 proposal.")],
    )
    card = _feed(client).json()["proposals"][0]
    client.patch(f"/tasks/{task['id']}", json={"title": "Book the boiler service for December"})

    stale = client.post(f"/agent/proposals/{card['id']}/apply")
    assert stale.status_code == 409
    assert stale.json()["detail"] == "The item changed since this was proposed. Nothing was applied."
    assert client.get(f"/tasks/{task['id']}").json()["status"] == "todo"
    assert _state(client)["proposals"] == []


def test_apply_waits_while_paused(client, house_clock, mistral):
    mistral([call("propose_change", FILTERS)], [say("1 proposal.")])
    card = _feed(client).json()["proposals"][0]
    client.post("/system/pause")
    blocked = client.post(f"/agent/proposals/{card['id']}/apply")
    assert blocked.status_code == 409
    assert blocked.json()["detail"] == "The house is paused. Nothing was applied."
    assert client.get("/tasks").json()["items"] == []
    client.post("/system/unpause")
    assert client.post(f"/agent/proposals/{card['id']}/apply").status_code == 200


def test_apply_a_note_and_a_new_commitment(client, house_clock, mistral):
    task = _add_task(client, detail="Annual service.")
    mistral(
        [
            call("add_note", {"kind": "task", "id": task["id"], "note": "Filters are 22 mm.", "reason": "Nick said."},
                 call_id="call_1"),
            call("propose_change", {"action": "create_commitment", "changes": {"title": "Pay the window cleaner",
                                    "due_on": "2026-11-07"}, "reason": "Due Saturday."}, call_id="call_2"),
        ],
        [say("Added 2 proposals.")],
    )
    cards = _feed(client).json()["proposals"]
    assert [card["action"] for card in cards] == ["add_note", "create_commitment"]
    for card in cards:
        assert client.post(f"/agent/proposals/{card['id']}/apply").status_code == 200
    assert client.get(f"/tasks/{task['id']}").json()["detail"] == "Annual service.\n2 Nov: Filters are 22 mm."
    [commitment] = client.get("/commitments").json()["items"]
    assert (commitment["title"], commitment["source"], commitment["status"]) == (
        "Pay the window cleaner",
        "assistant",
        "open",
    )


def test_not_now(client, house_clock, mistral):
    mistral([call("propose_change", FILTERS)], [say("1 proposal.")])
    card = _feed(client).json()["proposals"][0]
    dismissed = client.post(f"/agent/proposals/{card['id']}/dismiss")
    assert dismissed.status_code == 200
    assert dismissed.json()["status"] == "dismissed"
    assert client.post(f"/agent/proposals/{card['id']}/dismiss").status_code == 409
    assert client.post(f"/agent/proposals/{card['id']}/apply").status_code == 409
    assert client.get("/tasks").json()["items"] == []
    missing = client.post("/agent/proposals/00000000-0000-0000-0000-000000000000/apply")
    assert missing.status_code == 404


def test_action_requests_still_only_record(client, house_clock, mistral):
    mistral([call("propose_change", FILTERS)], [say("1 proposal.")])
    _feed(client)
    request = client.post("/action-requests", json={"title": "Message the plumber", "mode": "execute"}).json()
    approved = client.post(f"/approvals/{request['id']}/approve").json()
    assert approved["effect_applied"] is False
    assert approved["effect"]["applied"] is False
    assert client.get("/tasks").json()["items"] == []


# --- proactive reviews ------------------------------------------------------


def test_morning_review_runs_once_with_two_proposals(client, house_clock, mistral):
    _add_task(client, due_on="2026-11-02")
    _add_task(client, title="Fix the gate")
    state = _state(client)
    assert state["due"] == {"trigger": "morning_review", "window_key": "2026-11-02", "label": "Morning review"}

    fake = mistral(
        [call("get_state")],
        [
            call("propose_change", {"action": "create_task", "changes": {"title": "Buy hinges", "due_on": "2026-11-03"},
                                    "reason": "First step for the gate."}, call_id="a"),
            call("propose_change", {"action": "create_task", "changes": {"title": "Ring the boiler firm",
                                    "due_on": "2026-11-02"}, "reason": "Due today."}, call_id="b"),
            call("propose_change", {"action": "create_task", "changes": {"title": "Third idea"}, "reason": "x"},
                 call_id="c"),
        ],
        [say("Morning review: 2 proposals.")],
    )
    response = client.post("/agent/review", json=state["due"])
    assert response.status_code == 200
    body = response.json()
    assert body["trigger"] == "morning_review"
    assert [card["label"] for card in body["proposals"]] == ["Morning review", "Morning review"]
    assert fake.results()[-1]["ok"] is False
    assert "limit for this run (2)" in fake.results()[-1]["error"]
    packet = fake.calls[0][2]
    assert "Trigger: morning_review" in packet
    assert "Proposal limit: 2" in packet
    assert "\n\nContext:\n" not in packet
    assert "Book the boiler service (Due today · Medium · To do)" in packet

    again = client.post("/agent/review", json=state["due"])
    assert again.status_code == 409
    after = _state(client)
    assert after["due"] is None
    assert after["proactive_left_today"] == 1


def test_stale_item_card_cools_down_and_the_daily_cap_holds(client, db, house_clock, mistral):
    house_clock["now"] = london(2026, 11, 2, 14, 0)
    task = _add_task(client, status="doing")
    _set_updated_at(db, task["id"], london(2026, 10, 29, 9, 0))

    due = _state(client)["due"]
    assert due["trigger"] == "doing_stalled"
    assert due["label"] == "In progress, no update for 4 days"
    assert due["window_key"].endswith("#1")

    fake = mistral(
        [call("propose_change", {"action": "update_task", "id": task["id"], "changes": {"status": "done"},
                                 "reason": "Looks finished."})],
        [say("1 proposal.")],
    )
    card = client.post("/agent/review", json=due).json()["proposals"][0]
    assert card["label"] == "In progress, no update for 4 days"
    assert "Item: task " + task["id"] in fake.calls[0][2]
    assert "Proposal limit: 1" in fake.calls[0][2]
    follow = json.loads(fake.calls[0][2].split("\n\nContext:\n", 1)[1])
    assert follow["purpose"] == "follow_up"
    assert follow["schema_version"] == 1
    assert follow["focus"]["title"] == task["title"]
    assert _state(client)["due"] is None  # one proactive card at a time

    client.post(f"/agent/proposals/{card['id']}/dismiss")
    assert _state(client)["due"] is None  # resting for 72 hours

    house_clock["now"] = london(2026, 11, 5, 14, 1)
    due = _state(client)["due"]
    assert due["trigger"] == "doing_stalled"
    assert due["window_key"].endswith("#2")


def test_three_proactive_proposals_a_day_then_quiet(client, db, house_clock, mistral):
    for title in ("Gate", "Shed", "Gutter"):
        task = _add_task(client, title=title, status="doing")
        _set_updated_at(db, task["id"], london(2026, 10, 28, 9, 0))
    house_clock["now"] = london(2026, 11, 2, 12, 0)

    for _ in range(3):
        due = _state(client)["due"]
        assert due is not None
        task_id = due["window_key"].split(":")[1]
        mistral(
            [call("propose_change", {"action": "update_task", "id": task_id, "changes": {"status": "todo"},
                                     "reason": "Stalled."})],
            [say("1 proposal.")],
        )
        card = client.post("/agent/review", json=due).json()["proposals"][0]
        client.post(f"/agent/proposals/{card['id']}/dismiss")

    state = _state(client)
    assert state["proactive_left_today"] == 0
    assert state["due"] is None


def test_review_must_match_what_is_due(client, house_clock, mistral):
    fake = mistral()
    wrong = client.post("/agent/review", json={"trigger": "morning_review", "window_key": "2026-11-01"})
    assert wrong.status_code == 409
    assert wrong.json()["detail"] == "Nothing is due."
    house_clock["now"] = london(2026, 11, 2, 23, 0)
    late = client.post("/agent/review", json={"trigger": "morning_review", "window_key": "2026-11-02"})
    assert late.status_code == 409
    assert fake.calls == []


def test_summer_time_morning_window_through_the_api(client, house_clock, assistant_on):
    from datetime import datetime
    from zoneinfo import ZoneInfo

    house_clock["now"] = datetime(2026, 7, 15, 5, 0, tzinfo=ZoneInfo("UTC"))
    due = _state(client)["due"]
    assert due["trigger"] == "morning_review"
    assert due["window_key"] == "2026-07-15"
    house_clock["now"] = datetime(2026, 7, 15, 4, 59, tzinfo=ZoneInfo("UTC"))
    assert _state(client)["due"] is None


def test_proposals_are_hidden_while_paused(client, house_clock, mistral):
    mistral([call("propose_change", FILTERS)], [say("1 proposal.")])
    _feed(client)
    client.post("/system/pause")
    assert _state(client)["proposals"] == []
    client.post("/system/unpause")
    assert len(_state(client)["proposals"]) == 1


def test_last_reply_is_today_only(client, house_clock, mistral):
    mistral([say("Nothing to add.")])
    _feed(client)
    assert _state(client)["last_reply"]["text"] == "Nothing to add."
    house_clock["now"] = house_clock["now"] + timedelta(days=1)
    assert _state(client)["last_reply"] is None
