"""HTTP routes for auth, tasks, notes, and today."""

import sqlite3
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status

from organiser.auth import secret_matches
from organiser.config import get_settings
from organiser.db import db_session
from organiser.deps import require_auth
from organiser.schemas import (
    HealthOut,
    LoginIn,
    MeOut,
    NoteIn,
    NoteOut,
    NotePatch,
    OkOut,
    TaskIn,
    TaskOut,
    TaskPatch,
    TodayOut,
)
from organiser.store import (
    create_note,
    create_task,
    delete_note,
    delete_task,
    get_note,
    get_task,
    list_notes,
    list_tasks,
    tasks_due_on,
    update_note,
    update_task,
)
from organiser.tags import clean_one_tag

health_router = APIRouter(tags=["health"])
auth_router = APIRouter(prefix="/api/auth", tags=["auth"])
api_router = APIRouter(prefix="/api", dependencies=[Depends(require_auth)])


def _blank(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None


def _require_task(conn: sqlite3.Connection, task_id: int | None) -> None:
    if task_id is None:
        return
    if get_task(conn, task_id) is None:
        raise HTTPException(status_code=400, detail="Linked task does not exist")


@health_router.get("/api/health", response_model=HealthOut)
def health() -> HealthOut:
    return HealthOut()


@auth_router.post("/login", response_model=OkOut)
def login(body: LoginIn, request: Request) -> OkOut:
    settings = get_settings()
    if not secret_matches(body.password, settings.auth_secret):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid password")
    request.session["authenticated"] = True
    return OkOut()


@auth_router.post("/logout", response_model=OkOut)
def logout(request: Request) -> OkOut:
    request.session.clear()
    return OkOut()


@auth_router.get("/me", response_model=MeOut)
def me(request: Request) -> MeOut:
    require_auth(request)
    return MeOut(authenticated=True)


@api_router.get("/tasks", response_model=list[TaskOut])
def tasks_list(
    status_filter: Literal["todo", "doing", "done"] | None = Query(
        default=None, alias="status"
    ),
    priority: Literal["low", "medium", "high"] | None = None,
    due: date | None = None,
    q: str | None = Query(default=None, max_length=200),
) -> list[dict]:
    with db_session() as conn:
        return list_tasks(
            conn,
            status=status_filter,
            priority=priority,
            due=due,
            q=_blank(q),
        )


@api_router.post("/tasks", response_model=TaskOut, status_code=status.HTTP_201_CREATED)
def tasks_create(body: TaskIn) -> dict:
    with db_session() as conn:
        return create_task(conn, body.model_dump())


@api_router.get("/tasks/{task_id}", response_model=TaskOut)
def tasks_get(task_id: int) -> dict:
    with db_session() as conn:
        task = get_task(conn, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@api_router.patch("/tasks/{task_id}", response_model=TaskOut)
def tasks_patch(task_id: int, body: TaskPatch) -> dict:
    fields = body.model_dump(exclude_unset=True)
    if not fields:
        raise HTTPException(status_code=400, detail="No changes")
    with db_session() as conn:
        updated = update_task(conn, task_id, fields)
    if updated is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return updated


@api_router.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def tasks_delete(task_id: int) -> Response:
    with db_session() as conn:
        deleted = delete_task(conn, task_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Task not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@api_router.get("/notes", response_model=list[NoteOut])
def notes_list(
    q: str | None = Query(default=None, max_length=200),
    tag: str | None = Query(default=None, max_length=40),
    task_id: int | None = None,
) -> list[dict]:
    tag_value = _blank(tag)
    if tag_value is not None:
        try:
            tag_value = clean_one_tag(tag_value)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
    with db_session() as conn:
        return list_notes(
            conn,
            q=_blank(q),
            tag=tag_value,
            task_id=task_id,
            limit=500,
        )


@api_router.post("/notes", response_model=NoteOut, status_code=status.HTTP_201_CREATED)
def notes_create(body: NoteIn) -> dict:
    with db_session() as conn:
        _require_task(conn, body.task_id)
        return create_note(conn, body.model_dump())


@api_router.get("/notes/{note_id}", response_model=NoteOut)
def notes_get(note_id: int) -> dict:
    with db_session() as conn:
        note = get_note(conn, note_id)
    if note is None:
        raise HTTPException(status_code=404, detail="Note not found")
    return note


@api_router.patch("/notes/{note_id}", response_model=NoteOut)
def notes_patch(note_id: int, body: NotePatch) -> dict:
    fields = body.model_dump(exclude_unset=True)
    if not fields:
        raise HTTPException(status_code=400, detail="No changes")
    with db_session() as conn:
        if "task_id" in fields:
            _require_task(conn, fields["task_id"])
        updated = update_note(conn, note_id, fields)
    if updated is None:
        raise HTTPException(status_code=404, detail="Note not found")
    return updated


@api_router.delete("/notes/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
def notes_delete(note_id: int) -> Response:
    with db_session() as conn:
        deleted = delete_note(conn, note_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Note not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@api_router.get("/today", response_model=TodayOut)
def today(notes_limit: int = Query(default=20, ge=1, le=100)) -> dict:
    day = date.today()
    with db_session() as conn:
        return {
            "date": day,
            "tasks": tasks_due_on(conn, day),
            "notes": list_notes(conn, q=None, tag=None, task_id=None, limit=notes_limit),
        }
