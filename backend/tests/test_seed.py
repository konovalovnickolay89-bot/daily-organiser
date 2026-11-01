from sqlalchemy import func, select

from organiser.models import ActionRequest, Commitment, Task
from organiser.seed import seed_if_empty


def test_seed_is_idempotent_and_home_scoped(db):
    assert seed_if_empty(db) is True
    db.commit()
    first = db.scalar(select(func.count()).select_from(Task))
    assert first >= 4
    assert seed_if_empty(db) is False
    db.commit()
    assert db.scalar(select(func.count()).select_from(Task)) == first

    tasks = {row.title: row for row in db.scalars(select(Task)).all()}
    assert tasks["Put the bins out"].owner == "Nick"
    assert "Book the boiler service" in tasks

    requests = list(db.scalars(select(ActionRequest)).all())
    assert {row.mode for row in requests} == {"observe", "advise", "prepare", "execute"}
    assert all(row.effect_applied is False for row in requests)

    open_titles = set(db.scalars(select(Commitment.title).where(Commitment.status == "open")).all())
    assert "Collect the dry cleaning" in open_titles
    assert "Take the library books back" not in open_titles


def test_seeded_brief_and_execute_approval(client, db):
    seed_if_empty(db)
    db.commit()

    brief = client.get("/brief/morning").json()
    task_titles = [item["title"] for item in brief["sections"][0]["items"]]
    assert "Put the bins out" in task_titles
    assert "Replace the hallway bulb" in task_titles
    assert "Book the boiler service" not in task_titles
    commitment_titles = [item["title"] for item in brief["sections"][1]["items"]]
    assert "Collect the dry cleaning" in commitment_titles
    assert "Take the library books back" not in commitment_titles

    pending = client.get("/approvals").json()["items"]
    execute = next(item for item in pending if item["mode"] == "execute")
    decision = client.post(f"/approvals/{execute['id']}/approve").json()
    assert decision["effect_applied"] is False
    assert decision["effect"]["applied"] is False
    assert "nothing was sent" in decision["effect"]["summary"].lower()
