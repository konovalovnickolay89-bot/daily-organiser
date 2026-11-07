"""The reminder preview reads the rules and does not call Mistral."""

from datetime import date

from agent_fakes import london

from organiser.agent.mistral import MistralClient
from organiser.models import Task


def test_preview_is_quiet_and_lists_a_bounded_line(client, db, house_clock, assistant_on, monkeypatch):
    def boom(*args, **kwargs):
        raise AssertionError("The preview called Mistral.")

    monkeypatch.setattr(MistralClient, "complete", boom)
    monkeypatch.setattr(MistralClient, "embed", boom)
    monkeypatch.setattr(MistralClient, "start", boom)
    moment = london(2026, 11, 2, 23, 0)
    house_clock["now"] = moment
    db.add(
        Task(
            title="Meet a guest",
            due_on=date(2026, 10, 28),
            priority="low",
            status="todo",
            owner="Nick",
            created_at=moment,
            updated_at=moment,
        )
    )
    db.commit()
    assert client.post("/tasks", json={"title": "Water the plants", "due_on": "2026-10-28", "priority": "low"}).status_code == 201

    response = client.get("/agent/preview")
    assert response.status_code == 200
    body = response.json()
    assert body["calls_assistant"] is False
    assert body["quiet"] is True
    assert body["due"] is None
    assert body["held_because"] == "Quiet hours. Nothing is sent."
    assert body["quiet_hours"] == "22:00–05:59 Europe/London"
    titles = [item["title"] for item in body["candidates"]]
    assert titles == ["Water the plants"]
    assert len(body["candidates"]) <= 3
    assert body["local_reminders"] == "off"
    assert body["reminder_overdue"] == "off"
    assert body["reminder_stalled"] == "off"
    assert body["reminder_upcoming"] == "off"
    assert body["waiting_note"] is None
    assert body["candidates"][0]["type_on"] is False
    refused = client.post("/agent/reminders")
    assert refused.status_code == 200
    assert refused.json() == {
        "prepared": 0,
        "reason": "off",
        "calls_assistant": False,
        "summary": None,
        "assessment": "skipped",
    }
    assert client.get("/agent").json()["proposals"] == []


def _worth(messages):
    import json

    item = json.loads(messages[-1]["content"])["untrusted_item"]
    return json.dumps(
        {
            "worth_flagging": True,
            "ref_id": item["ref_id"],
            "rationale": f"The log says {item['rule_reason']}.",
            "next_step": "Have a look at this one.",
        }
    )


def test_local_reminders_stay_off_until_saved_and_respect_quiet_hours(client, db, house_clock, reminder_ai):
    fake = reminder_ai(_worth)
    moment = london(2026, 11, 2, 8, 0)
    house_clock["now"] = moment
    saved = client.post("/system/local-reminders", json={"enabled": True}).json()
    assert saved["local_reminders"] == "on"
    assert saved["reminder_overdue"] == "off"
    assert saved["reminder_stalled"] == "off"
    assert saved["reminder_upcoming"] == "off"
    turned = client.post("/system/local-reminders", json={"overdue": True}).json()
    assert turned["local_reminders"] == "on"
    assert turned["reminder_overdue"] == "on"
    house_clock["now"] = london(2026, 11, 2, 23, 0)
    quiet = client.post("/agent/reminders")
    assert quiet.json()["prepared"] == 0
    assert quiet.json()["reason"] == "Quiet hours. Nothing is sent."
    assert quiet.json()["calls_assistant"] is False
    house_clock["now"] = moment
    db.add(
        Task(
            title="Meet a guest",
            due_on=date(2026, 10, 28),
            priority="low",
            status="todo",
            owner="Nick",
            created_at=moment,
            updated_at=moment,
        )
    )
    db.commit()
    assert client.post("/tasks", json={"title": "Water the plants", "due_on": "2026-10-28", "priority": "low"}).status_code == 201
    made = client.post("/agent/reminders")
    assert made.status_code == 200
    body = made.json()
    assert body["prepared"] == 1
    assert body["calls_assistant"] is True
    assert body["assessment"] == "assessed"
    assert "Water the plants" in body["summary"]
    assert "guest" not in fake.calls[0]["messages"][-1]["content"].lower()
    assert "guest" not in body["summary"].lower()
    again = client.post("/agent/reminders")
    assert again.json()["prepared"] == 0
    assert again.json()["reason"] == "A reminder is already waiting."
    proposals = client.get("/agent").json()["proposals"]
    assert len(proposals) == 1
    assert proposals[0]["label"] == "Assessed reminder"
    assert proposals[0]["action"] == "add_note"
    assert proposals[0]["memories_used"] == 0
    assert client.post("/system/local-reminders", json={"enabled": False}).json()["local_reminders"] == "off"
    restored = client.post("/system/local-reminders", json={"enabled": True}).json()
    assert restored["local_reminders"] == "on"
    assert restored["reminder_overdue"] == "on"
    assert restored["reminder_stalled"] == "off"
    assert client.post("/system/pause").status_code == 200
    paused = client.post("/agent/reminders")
    assert paused.json()["prepared"] == 0
    assert paused.json()["reason"] == "The house is paused."
    assert paused.json()["calls_assistant"] is False
