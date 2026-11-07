"""The reminder preview reads the rules and does not call Mistral."""

from datetime import date

from agent_fakes import london

from organiser.agent.mistral import MistralClient
from organiser.models import Task


def test_preview_is_quiet_and_lists_a_bounded_line(client, db, house_clock, assistant_on, monkeypatch):
    def boom(self, *args, **kwargs):
        raise AssertionError("The preview called Mistral.")

    monkeypatch.setattr(MistralClient, "__init__", boom)
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
