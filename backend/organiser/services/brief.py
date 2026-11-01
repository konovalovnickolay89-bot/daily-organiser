from datetime import date

from sqlalchemy import case, or_, select
from sqlalchemy.orm import Session

from organiser.domain import PRIORITY_LABELS, TASK_STATUS_LABELS
from organiser.models import Commitment, Task
from organiser.timeutil import utcnow


def _priority_order():
    return case(
        (Task.priority == "high", 0),
        (Task.priority == "medium", 1),
        else_=2,
    )


def _day_month(value: date) -> str:
    return f"{value.day} {value.strftime('%b')}"


def _task_meta(task: Task, today: date) -> str:
    if task.due_on is None:
        when = "No date"
    elif task.due_on < today:
        when = "Overdue"
    elif task.due_on == today:
        when = "Due today"
    else:
        when = _day_month(task.due_on)
    priority = PRIORITY_LABELS.get(task.priority, task.priority)
    status = TASK_STATUS_LABELS.get(task.status, task.status)
    return f"{when} · {priority} · {status}"


def _task_summary(tasks: list[Task], today: date) -> str:
    if not tasks:
        return "Nothing needs doing."
    due_today = sum(1 for task in tasks if task.due_on == today)
    overdue = sum(1 for task in tasks if task.due_on is not None and task.due_on < today)
    undated = sum(1 for task in tasks if task.due_on is None)
    parts: list[str] = []
    if due_today:
        parts.append(f"{due_today} due today")
    if overdue:
        parts.append(f"{overdue} overdue")
    if undated:
        parts.append(f"{undated} with no date")
    return ", ".join(parts)


def _commitment_meta(commitment: Commitment) -> str:
    if commitment.due_on is None:
        return f"Open · {commitment.owner}"
    return f"Due {_day_month(commitment.due_on)} · {commitment.owner}"


def morning_brief(session: Session, today: date, paused: bool) -> dict:
    tasks = list(
        session.scalars(
            select(Task)
            .where(Task.status != "done")
            .where(or_(Task.due_on.is_(None), Task.due_on <= today))
            .order_by(Task.due_on.asc().nulls_last(), _priority_order(), Task.title.asc())
            .limit(20)
        ).all()
    )
    commitments = list(
        session.scalars(
            select(Commitment)
            .where(Commitment.status == "open")
            .order_by(Commitment.due_on.asc().nulls_last(), Commitment.title.asc())
            .limit(20)
        ).all()
    )
    open_count = len(commitments)
    commitment_summary = "None open." if open_count == 0 else f"{open_count} open"

    note = None
    if paused:
        note = "The house is paused. This brief is only a reading."

    return {
        "title": "Morning brief",
        "as_of": utcnow(),
        "house_date": today,
        "paused": paused,
        "note": note,
        "sections": [
            {
                "key": "tasks",
                "title": "Tasks",
                "placeholder": False,
                "summary": _task_summary(tasks, today),
                "items": [
                    {
                        "id": task.id,
                        "title": task.title,
                        "detail": task.detail,
                        "meta": _task_meta(task, today),
                    }
                    for task in tasks
                ],
            },
            {
                "key": "commitments",
                "title": "Open commitments",
                "placeholder": False,
                "summary": commitment_summary,
                "items": [
                    {
                        "id": commitment.id,
                        "title": commitment.title,
                        "detail": commitment.detail,
                        "meta": _commitment_meta(commitment),
                    }
                    for commitment in commitments
                ],
            },
            {
                "key": "appointments",
                "title": "Appointments",
                "placeholder": True,
                "summary": "No diary is connected. Appointments will show here when one is.",
                "items": [],
            },
            {
                "key": "shopping",
                "title": "Shopping",
                "placeholder": True,
                "summary": "No shop is connected. Nothing is ordered from this screen.",
                "items": [],
            },
            {
                "key": "weather",
                "title": "Weather",
                "placeholder": True,
                "summary": "Weather is not connected. A forecast will sit here later.",
                "items": [],
            },
        ],
    }
