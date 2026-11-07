"""Per-type reminder switches. Master off wins. Each type defaults off."""

from datetime import timedelta

from sqlalchemy import delete, func, select

from agent_fakes import london

from organiser.agent.mistral import MistralClient
from organiser.agent.rules import window_base
from organiser.models import AgentProposal, AgentRun, Commitment, Task


def _on(client, **flags):
    response = client.post("/system/local-reminders", json=flags)
    assert response.status_code == 200, response.text
    return response.json()


def _prepare(client):
    response = client.post("/agent/reminders")
    assert response.status_code == 200, response.text
    return response.json()


def _overdue(db, moment, title):
    db.add(
        Task(
            title=title,
            due_on=moment.date() - timedelta(days=4),
            priority="low",
            status="todo",
            owner="Nick",
            created_at=moment,
            updated_at=moment,
        )
    )


def _stalled(db, moment, title):
    db.add(
        Task(
            title=title,
            due_on=moment.date(),
            priority="low",
            status="doing",
            owner="Nick",
            created_at=moment - timedelta(days=5),
            updated_at=moment - timedelta(days=5),
        )
    )


def _upcoming(db, moment, title):
    db.add(
        Commitment(
            title=title,
            status="open",
            owner="Nick",
            due_on=moment.date() + timedelta(days=1),
            created_at=moment,
            updated_at=moment,
        )
    )


def test_each_type_prepares_only_itself(client, db, house_clock, monkeypatch):
    monkeypatch.setattr(MistralClient, "__init__", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("called")))
    moment = london(2026, 11, 2, 8, 0)
    house_clock["now"] = moment
    _overdue(db, moment, "Water the plants")
    db.commit()
    _on(client, enabled=True, overdue=True)
    made = _prepare(client)
    assert made["prepared"] == 1
    assert made["calls_assistant"] is False
    assert "Water the plants" in made["summary"]
    assert client.get("/agent").json()["proposals"][0]["rule"] == "overdue_lingering"

    client.post(f"/agent/proposals/{client.get('/agent').json()['proposals'][0]['id']}/dismiss")
    _on(client, overdue=False, stalled=True)
    _stalled(db, moment, "Mend the stair rod")
    db.commit()
    stalled = _prepare(client)
    assert stalled["prepared"] == 1
    assert "Mend the stair rod" in stalled["summary"]
    assert "Water the plants" not in stalled["summary"]

    client.post(f"/agent/proposals/{client.get('/agent').json()['proposals'][0]['id']}/dismiss")
    _on(client, stalled=False, upcoming=True)
    _upcoming(db, moment, "Return the spare key")
    db.commit()
    upcoming = _prepare(client)
    assert upcoming["prepared"] == 1
    assert upcoming["reason"] == "commitment_due_soon"
    assert "Return the spare key" in upcoming["summary"]


def test_a_lower_type_is_prepared_when_higher_ones_are_off(client, db, house_clock):
    moment = london(2026, 11, 2, 8, 0)
    house_clock["now"] = moment
    _stalled(db, moment, "Mend the stair rod")
    _overdue(db, moment, "Water the plants")
    _upcoming(db, moment, "Return the spare key")
    db.commit()
    _on(client, enabled=True, upcoming=True)
    made = _prepare(client)
    assert made["prepared"] == 1
    assert made["reason"] == "commitment_due_soon"
    titles = [item["summary"] for item in client.get("/agent").json()["proposals"]]
    assert len(titles) == 1
    assert "Return the spare key" in titles[0]
    assert "stair" not in titles[0].lower()
    assert "plants" not in titles[0].lower()


def test_all_types_off_prepares_nothing(client, db, house_clock):
    moment = london(2026, 11, 2, 8, 0)
    house_clock["now"] = moment
    _stalled(db, moment, "Mend the stair rod")
    _overdue(db, moment, "Water the plants")
    _upcoming(db, moment, "Return the spare key")
    db.commit()
    facts = _on(client, enabled=True)
    assert facts["reminder_overdue"] == "off"
    assert facts["reminder_stalled"] == "off"
    assert facts["reminder_upcoming"] == "off"
    made = _prepare(client)
    assert made["prepared"] == 0
    assert made["reason"] == "Those reminder types are off. Nothing new was prepared."
    assert made["calls_assistant"] is False
    assert client.get("/agent").json()["proposals"] == []


def test_master_off_wins_and_saved_types_survive(client, db, house_clock):
    moment = london(2026, 11, 2, 8, 0)
    house_clock["now"] = moment
    _overdue(db, moment, "Water the plants")
    db.commit()
    _on(client, enabled=True, overdue=True, stalled=True)
    off = _on(client, enabled=False)
    assert off["local_reminders"] == "off"
    assert off["reminder_overdue"] == "on"
    preview = client.get("/agent/preview").json()
    water = next(item for item in preview["candidates"] if item["title"] == "Water the plants")
    assert water["type_on"] is True
    assert preview["local_reminders"] == "off"
    assert off["reminder_stalled"] == "on"
    assert off["reminder_upcoming"] == "off"
    refused = _prepare(client)
    assert refused == {"prepared": 0, "reason": "off", "calls_assistant": False, "summary": None}
    assert client.get("/agent").json()["proposals"] == []
    restored = _on(client, enabled=True)
    assert restored["local_reminders"] == "on"
    assert restored["reminder_overdue"] == "on"
    assert restored["reminder_stalled"] == "on"
    assert restored["reminder_upcoming"] == "off"
    reloaded = client.get("/system/facts").json()
    assert reloaded["reminder_overdue"] == "on"
    assert reloaded["reminder_stalled"] == "on"
    made = _prepare(client)
    assert made["prepared"] == 1
    assert made["reason"] == "overdue_lingering"
    assert "Water the plants" in made["summary"]


def test_an_old_client_cannot_turn_types_on(client):
    saved = _on(client, enabled=True)
    assert saved["local_reminders"] == "on"
    assert saved["reminder_overdue"] == "off"
    assert saved["reminder_stalled"] == "off"
    assert saved["reminder_upcoming"] == "off"
    assert client.post("/system/local-reminders", json={}).status_code == 422
    assert client.post("/system/local-reminders", json={"enabled": True, "other": True}).status_code == 422
    assert client.post("/system/local-reminders", json={"overdue": "yes"}).status_code == 422
    assert client.get("/system/facts").json()["reminder_overdue"] == "off"
    assert client.get("/system/facts").json()["reminder_overdue"] == "off"


def test_a_disabled_type_leaves_its_waiting_card(client, db, house_clock):
    moment = london(2026, 11, 2, 8, 0)
    house_clock["now"] = moment
    _overdue(db, moment, "Water the plants")
    _upcoming(db, moment, "Return the spare key")
    db.commit()
    _on(client, enabled=True, overdue=True)
    assert _prepare(client)["prepared"] == 1
    _on(client, overdue=False, upcoming=True)
    again = _prepare(client)
    assert again["prepared"] == 0
    assert again["reason"] == (
        "Overdue tasks are off. A reminder of that type is still waiting, "
        "so the card was left in place and no new card was prepared."
    )
    proposals = client.get("/agent").json()["proposals"]
    assert len(proposals) == 1
    assert proposals[0]["status"] == "pending"
    assert proposals[0]["rule"] == "overdue_lingering"
    preview = client.get("/agent/preview").json()
    assert preview["waiting_note"] == again["reason"]
    assert "Return the spare key" not in preview["waiting_note"]


def test_quiet_hours_pause_dedupe_and_caps(client, db, house_clock):
    moment = london(2026, 11, 2, 8, 0)
    house_clock["now"] = moment
    _overdue(db, moment, "Water the plants")
    db.commit()
    _on(client, enabled=True, overdue=True)
    house_clock["now"] = london(2026, 11, 2, 22, 0)
    quiet = _prepare(client)
    assert quiet["prepared"] == 0
    assert quiet["reason"] == "Quiet hours. Nothing is sent."
    house_clock["now"] = london(2026, 11, 2, 5, 59)
    assert _prepare(client)["reason"] == "Quiet hours. Nothing is sent."
    house_clock["now"] = moment
    made = _prepare(client)
    assert made["prepared"] == 1
    proposal_id = client.get("/agent").json()["proposals"][0]["id"]
    assert client.post(f"/agent/proposals/{proposal_id}/dismiss").status_code == 200
    again = _prepare(client)
    assert again["prepared"] == 0
    assert again["reason"] == "nothing due"
    assert client.get("/agent").json()["proposals"] == []
    db.expire_all()
    assert db.scalar(select(AgentProposal.status)) == "dismissed"
    resting = db.scalar(select(Task).where(Task.title == "Water the plants"))
    assert resting is not None

    duplicate = Task(
        title="Fold the towels",
        due_on=moment.date() - timedelta(days=4),
        priority="low",
        status="todo",
        owner="Nick",
        created_at=moment,
        updated_at=moment,
    )
    db.add(duplicate)
    db.flush()
    db.add(
        AgentRun(
            trigger="overdue_lingering",
            window_key=f"{window_base('task', duplicate.id, duplicate.updated_at)}#1",
            status="done",
            started_at=moment - timedelta(days=90),
            finished_at=moment - timedelta(days=90),
        )
    )
    db.commit()
    raced = _prepare(client)
    assert raced["prepared"] == 0
    assert raced["reason"] == "already prepared"
    assert client.get("/agent").json()["proposals"] == []

    for index in range(3):
        db.add(
            AgentProposal(
                origin="proactive",
                rule="overdue_lingering",
                label="Local reminder",
                action="add_note",
                changes={"note": "cap"},
                summary=f"Cap {index}",
                reason="Prepared locally.",
                status="dismissed",
                created_at=moment,
            )
        )
    db.commit()
    reminders = _prepare(client)
    assert reminders["prepared"] == 0
    assert reminders["reason"] == "The daily reminder cap is spent."
    db.execute(delete(AgentProposal).where(AgentProposal.summary.like("Cap %")))
    db.commit()

    _on(client, overdue=False, stalled=True)
    _stalled(db, moment, "Mend the stair rod")
    for index in range(12):
        db.add(AgentRun(trigger="feed", window_key=f"feed:cap-{index}", status="done", started_at=moment, finished_at=moment))
    db.commit()
    capped = _prepare(client)
    assert capped["prepared"] == 0
    assert capped["reason"] == "The daily run cap is spent."
    assert client.post("/system/pause").status_code == 200
    db.execute(delete(AgentRun).where(AgentRun.trigger == "feed"))
    db.commit()
    paused = _prepare(client)
    assert paused["prepared"] == 0
    assert paused["reason"] == "The house is paused."
    assert client.get("/agent").json()["proposals"] == []
    assert db.scalar(select(func.count()).select_from(AgentProposal)) == 1
