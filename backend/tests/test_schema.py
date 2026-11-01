import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

from organiser.models import ActionRequest


def test_ops_tables_exist(db):
    names = set(inspect(db.get_bind()).get_table_names())
    assert {"tasks", "commitments", "events", "action_requests", "system_state"} <= names


def test_actionable_records_have_owner_and_status(db):
    inspector = inspect(db.get_bind())
    for table in ("tasks", "commitments", "action_requests"):
        columns = {column["name"]: column for column in inspector.get_columns(table)}
        assert columns["owner"]["nullable"] is False
        assert columns["status"]["nullable"] is False
    event_columns = {column["name"] for column in inspector.get_columns("events")}
    assert "owner" in event_columns
    assert "kind" in event_columns
    assert "status" not in event_columns
    state_columns = {column["name"]: column for column in inspector.get_columns("system_state")}
    assert {"paused", "activity", "status_text", "arrived_at"} <= set(state_columns)
    assert state_columns["arrived_at"]["nullable"] is True


def test_task_status_is_constrained(db):
    db.execute(
        text(
            "INSERT INTO tasks (id, title, priority, status, owner) "
            "VALUES (gen_random_uuid(), 'Bins', 'low', 'todo', 'Nick')"
        )
    )
    db.commit()
    with pytest.raises(IntegrityError):
        db.execute(text("UPDATE tasks SET status = 'later'"))
        db.commit()
    db.rollback()


def test_effect_cannot_be_marked_applied(db):
    db.add(ActionRequest(title="Message the plumber", mode="execute", status="pending", owner="Nick"))
    db.commit()
    with pytest.raises(IntegrityError):
        db.execute(text("UPDATE action_requests SET effect_applied = true"))
        db.commit()
    db.rollback()
