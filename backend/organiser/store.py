"""SQL for tasks and notes. Routes own HTTP errors; this module owns rows."""

import sqlite3
from datetime import date, datetime

from organiser.tags import join_tags, split_tags

MAX_LIST = 500

_TASK_COLUMNS = {"title", "due_date", "priority", "status", "recurring"}
_NOTE_COLUMNS = {"body", "tags", "task_id"}


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _contains(value: str) -> str:
    return f"%{_escape_like(value)}%"


def task_from_row(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "title": row["title"],
        "due_date": row["due_date"],
        "priority": row["priority"],
        "status": row["status"],
        "recurring": bool(row["recurring"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def note_from_row(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "body": row["body"],
        "tags": split_tags(row["tags"]),
        "task_id": row["task_id"],
        "task_title": row["task_title"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


_NOTE_SELECT = """
SELECT
    notes.id,
    notes.body,
    notes.tags,
    notes.task_id,
    notes.created_at,
    notes.updated_at,
    tasks.title AS task_title
FROM notes
LEFT JOIN tasks ON tasks.id = notes.task_id
"""


def get_task(conn: sqlite3.Connection, task_id: int) -> dict | None:
    row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if row is None:
        return None
    return task_from_row(row)


def list_tasks(
    conn: sqlite3.Connection,
    *,
    status: str | None,
    priority: str | None,
    due: date | None,
    q: str | None,
) -> list[dict]:
    clauses: list[str] = []
    params: list[object] = []
    if status:
        clauses.append("status = ?")
        params.append(status)
    if priority:
        clauses.append("priority = ?")
        params.append(priority)
    if due is not None:
        clauses.append("due_date = ?")
        params.append(due.isoformat())
    if q:
        clauses.append("title LIKE ? ESCAPE '\\'")
        params.append(_contains(q))
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    params.append(MAX_LIST)
    rows = conn.execute(
        f"""
        SELECT * FROM tasks
        {where}
        ORDER BY
            CASE WHEN due_date IS NULL THEN 1 ELSE 0 END,
            due_date,
            CASE priority WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END,
            id DESC
        LIMIT ?
        """,
        params,
    ).fetchall()
    return [task_from_row(row) for row in rows]


def create_task(conn: sqlite3.Connection, fields: dict) -> dict:
    now = now_iso()
    due = fields.get("due_date")
    cur = conn.execute(
        """
        INSERT INTO tasks
            (title, due_date, priority, status, recurring, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            fields["title"],
            due.isoformat() if due else None,
            fields["priority"],
            fields["status"],
            1 if fields["recurring"] else 0,
            now,
            now,
        ),
    )
    created = get_task(conn, int(cur.lastrowid))
    if created is None:
        raise RuntimeError("Task insert did not return a row")
    return created


def update_task(conn: sqlite3.Connection, task_id: int, fields: dict) -> dict | None:
    if get_task(conn, task_id) is None:
        return None
    assignments: list[str] = []
    params: list[object] = []
    for key, value in fields.items():
        if key not in _TASK_COLUMNS:
            continue
        assignments.append(f"{key} = ?")
        if key == "recurring":
            params.append(1 if value else 0)
        elif key == "due_date":
            params.append(value.isoformat() if value else None)
        else:
            params.append(value)
    if not assignments:
        return get_task(conn, task_id)
    assignments.append("updated_at = ?")
    params.append(now_iso())
    params.append(task_id)
    conn.execute(
        f"UPDATE tasks SET {', '.join(assignments)} WHERE id = ?",
        params,
    )
    return get_task(conn, task_id)


def delete_task(conn: sqlite3.Connection, task_id: int) -> bool:
    cur = conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    return cur.rowcount > 0


def tasks_due_on(conn: sqlite3.Connection, day: date) -> list[dict]:
    rows = conn.execute(
        """
        SELECT * FROM tasks
        WHERE due_date = ?
        ORDER BY
            CASE priority WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END,
            CASE status WHEN 'doing' THEN 0 WHEN 'todo' THEN 1 ELSE 2 END,
            title COLLATE NOCASE,
            id
        """,
        (day.isoformat(),),
    ).fetchall()
    return [task_from_row(row) for row in rows]


def get_note(conn: sqlite3.Connection, note_id: int) -> dict | None:
    row = conn.execute(
        f"{_NOTE_SELECT} WHERE notes.id = ?",
        (note_id,),
    ).fetchone()
    if row is None:
        return None
    return note_from_row(row)


def list_notes(
    conn: sqlite3.Connection,
    *,
    q: str | None,
    tag: str | None,
    task_id: int | None,
    limit: int,
) -> list[dict]:
    clauses: list[str] = []
    params: list[object] = []
    if q:
        pattern = _contains(q)
        clauses.append(
            "(notes.body LIKE ? ESCAPE '\\' OR notes.tags LIKE ? ESCAPE '\\')"
        )
        params.extend([pattern, pattern])
    if tag:
        clauses.append("(',' || notes.tags || ',') LIKE ? ESCAPE '\\'")
        params.append(f"%,{_escape_like(tag)},%")
    if task_id is not None:
        clauses.append("notes.task_id = ?")
        params.append(task_id)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    params.append(limit)
    rows = conn.execute(
        f"""
        {_NOTE_SELECT}
        {where}
        ORDER BY notes.created_at DESC, notes.id DESC
        LIMIT ?
        """,
        params,
    ).fetchall()
    return [note_from_row(row) for row in rows]


def create_note(conn: sqlite3.Connection, fields: dict) -> dict:
    now = now_iso()
    cur = conn.execute(
        """
        INSERT INTO notes (body, tags, task_id, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            fields["body"],
            join_tags(fields.get("tags") or []),
            fields.get("task_id"),
            now,
            now,
        ),
    )
    created = get_note(conn, int(cur.lastrowid))
    if created is None:
        raise RuntimeError("Note insert did not return a row")
    return created


def update_note(conn: sqlite3.Connection, note_id: int, fields: dict) -> dict | None:
    if get_note(conn, note_id) is None:
        return None
    assignments: list[str] = []
    params: list[object] = []
    for key, value in fields.items():
        if key not in _NOTE_COLUMNS:
            continue
        assignments.append(f"{key} = ?")
        if key == "tags":
            params.append(join_tags(value or []))
        else:
            params.append(value)
    if not assignments:
        return get_note(conn, note_id)
    assignments.append("updated_at = ?")
    params.append(now_iso())
    params.append(note_id)
    conn.execute(
        f"UPDATE notes SET {', '.join(assignments)} WHERE id = ?",
        params,
    )
    return get_note(conn, note_id)


def delete_note(conn: sqlite3.Connection, note_id: int) -> bool:
    cur = conn.execute("DELETE FROM notes WHERE id = ?", (note_id,))
    return cur.rowcount > 0
