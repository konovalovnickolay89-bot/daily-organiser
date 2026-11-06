from datetime import date
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import case, select
from sqlalchemy.orm import Session

from organiser.config import get_settings
from organiser.db import get_db
from organiser.domain import Priority, TaskStatus
from organiser.models import Task
from organiser.schemas import TaskCreate, TaskList, TaskRead, TaskUpdate, apply_changes
from organiser.scope import require_house_fields
from organiser.services.activity import record_line
from organiser.timeutil import house_today

router = APIRouter(prefix="/tasks", tags=["tasks"])


def _priority_order():
    return case(
        (Task.priority == "high", 0),
        (Task.priority == "medium", 1),
        else_=2,
    )


def _get(session: Session, task_id: UUID) -> Task:
    row = session.get(Task, task_id)
    if row is None:
        raise HTTPException(status_code=404, detail="No such task.")
    return row


def _values(payload) -> dict:
    data = payload.model_dump()
    data["priority"] = data["priority"].value
    data["status"] = data["status"].value
    return data


@router.get("", response_model=TaskList)
def list_tasks(
    session: Session = Depends(get_db),
    status: TaskStatus | None = None,
    owner: str | None = None,
    priority: Priority | None = None,
    due_on: date | None = None,
    scope: Literal["all", "today"] = "all",
    limit: int = Query(default=100, ge=1, le=200),
) -> TaskList:
    statement = select(Task)
    if status is not None:
        statement = statement.where(Task.status == status.value)
    elif scope == "today":
        statement = statement.where(Task.status != "done")
    if owner:
        statement = statement.where(Task.owner == owner)
    if priority is not None:
        statement = statement.where(Task.priority == priority.value)
    if due_on is not None:
        statement = statement.where(Task.due_on == due_on)
    elif scope == "today":
        today = house_today(get_settings().house_timezone)
        statement = statement.where(Task.due_on.is_not(None), Task.due_on <= today)
    statement = statement.order_by(
        Task.due_on.asc().nulls_last(),
        _priority_order(),
        Task.title.asc(),
    ).limit(limit)
    return TaskList(items=list(session.scalars(statement).all()))


@router.post("", response_model=TaskRead, status_code=201)
def create_task(payload: TaskCreate, session: Session = Depends(get_db)) -> Task:
    require_house_fields(payload, "title", "detail", "owner")
    row = Task(**_values(payload))
    session.add(row)
    record_line(
        session,
        kind="task",
        title=f"Added: {row.title}",
        body="Added in the house log. Nothing outside it was changed.",
    )
    session.commit()
    session.refresh(row)
    return row


@router.get("/{task_id}", response_model=TaskRead)
def get_task(task_id: UUID, session: Session = Depends(get_db)) -> Task:
    return _get(session, task_id)


@router.patch("/{task_id}", response_model=TaskRead)
def update_task(task_id: UUID, payload: TaskUpdate, session: Session = Depends(get_db)) -> Task:
    require_house_fields(payload, "title", "detail", "owner")
    row = _get(session, task_id)
    apply_changes(row, payload)
    session.commit()
    session.refresh(row)
    return row


@router.delete("/{task_id}", status_code=204)
def delete_task(task_id: UUID, session: Session = Depends(get_db)) -> None:
    row = _get(session, task_id)
    session.delete(row)
    session.commit()
