"""The five functions Mistral may call, run here in the house.

Reads return household fields only. ``propose_change`` and ``add_note`` store a
pending proposal and change nothing else. Every refusal is enforced here, not
left to the instructions, and comes back to the model as
``{"ok": false, "error": ...}`` so it can correct itself. A handler never raises
into the run except on a database fault.
"""

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any, Literal
from uuid import UUID
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session

from organiser.agent.cards import DETAIL_LIMIT, note_line, summarise, with_note
from organiser.models import AgentProposal, AgentRun, Commitment, Task
from organiser.schemas import CommitmentCreate, CommitmentUpdate, TaskCreate, TaskUpdate
from organiser.services.system import ensure_system_state

PROPOSAL_DETAIL_LIMIT = 1000
REASON_LIMIT = 300

ALLOWED_FIELDS: dict[str, frozenset[str]] = {
    "create_task": frozenset({"title", "detail", "due_on", "priority"}),
    "update_task": frozenset({"title", "detail", "due_on", "priority", "status"}),
    "create_commitment": frozenset({"title", "detail", "due_on"}),
    "update_commitment": frozenset({"title", "detail", "due_on", "status"}),
}

_SCHEMAS: dict[str, type[BaseModel]] = {
    "create_task": TaskCreate,
    "update_task": TaskUpdate,
    "create_commitment": CommitmentCreate,
    "update_commitment": CommitmentUpdate,
}

_MODELS: dict[str, type] = {"task": Task, "commitment": Commitment}


class Refused(Exception):
    """A function refused its arguments. The message goes back to the model."""


@dataclass
class RunContext:
    session: Session
    now: datetime
    tz_name: str
    run: AgentRun
    origin: Literal["feed", "proactive"]
    rule: str
    label: str
    max_proposals: int
    proposals: list[AgentProposal] = field(default_factory=list)

    @property
    def local_now(self) -> datetime:
        return self.now.astimezone(ZoneInfo(self.tz_name))

    @property
    def today(self) -> date:
        return self.local_now.date()


class _Args(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SearchArgs(_Args):
    text: str | None = Field(default=None, max_length=100)
    kind: Literal["task", "commitment", "any"] = "any"
    status: Literal["todo", "doing", "done", "open", "kept", "dropped"] | None = None
    due_from: date | None = None
    due_to: date | None = None
    limit: int = Field(default=10, ge=1, le=20)


class ItemArgs(_Args):
    kind: Literal["task", "commitment"]
    id: str


class ProposeArgs(_Args):
    action: Literal["create_task", "update_task", "create_commitment", "update_commitment"]
    id: str | None = None
    changes: dict[str, Any]
    reason: str = Field(max_length=REASON_LIMIT)


class NoteArgs(_Args):
    kind: Literal["task", "commitment"]
    id: str
    note: str = Field(min_length=1, max_length=300)
    reason: str = Field(max_length=REASON_LIMIT)


# --- helpers ---------------------------------------------------------------


def _first_error(exc: ValidationError) -> str:
    error = exc.errors()[0]
    where = ".".join(str(part) for part in error.get("loc", ()) if part != "__root__")
    return f"{where}: {error['msg']}" if where else error["msg"]


def _parse(model: type[BaseModel], args: dict) -> Any:
    try:
        return model.model_validate(args)
    except ValidationError as exc:
        raise Refused(_first_error(exc)) from None


def _arguments(raw: Any) -> dict:
    if raw is None or raw == "":
        return {}
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            value = json.loads(raw)
        except ValueError:
            raise Refused("The arguments are not valid JSON.") from None
        if isinstance(value, dict):
            return value
    raise Refused("The arguments must be a JSON object.")


def _iso(value: date | datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _clip(text: str | None, limit: int) -> str | None:
    if text is None:
        return None
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _load(session: Session, kind: str, raw_id: str) -> Task | Commitment:
    try:
        item_id = UUID(str(raw_id))
    except ValueError:
        raise Refused(f"{raw_id!r} is not a valid id. Use an id from search_items.") from None
    row = session.get(_MODELS[kind], item_id)
    if row is None:
        raise Refused(f"No {kind} has the id {item_id}. Use search_items.")
    return row


def _brief(kind: str, row: Task | Commitment, *, detail_limit: int | None = 200) -> dict:
    item = {
        "kind": kind,
        "id": str(row.id),
        "title": row.title,
        "status": row.status,
        "due_on": _iso(row.due_on),
        "detail": _clip(row.detail, detail_limit) if detail_limit else row.detail,
        "updated_at": _iso(row.updated_at),
    }
    if kind == "task":
        item["priority"] = row.priority
    return item


def _is_open(item: dict) -> bool:
    return item["status"] in ("todo", "doing", "open")


def _reason(text: str) -> str:
    reason = " ".join(text.split())
    if not reason:
        raise Refused("reason is empty. Say why in under 20 words.")
    return reason


def _guard(ctx: RunContext) -> None:
    if ensure_system_state(ctx.session).paused:
        raise Refused("The house is paused. Propose nothing and stop.")
    if len(ctx.proposals) >= ctx.max_proposals:
        raise Refused(f"The proposal limit for this run ({ctx.max_proposals}) is reached. Stop proposing and reply.")


def _pending():
    return select(AgentProposal).where(AgentProposal.status == "pending")


def _no_waiting_for_item(ctx: RunContext, kind: str, item_id: UUID) -> None:
    waiting = ctx.session.scalars(
        _pending().where(AgentProposal.ref_type == kind, AgentProposal.ref_id == item_id).limit(1)
    ).first()
    if waiting is not None:
        raise Refused(f"A proposal for this {kind} is already waiting: {waiting.summary}. Leave it.")


def _no_duplicate_create(ctx: RunContext, action: str, kind: str, title: str) -> None:
    lowered = title.strip().lower()
    if kind == "task":
        existing = ctx.session.scalars(
            select(Task).where(Task.status != "done", func.lower(Task.title) == lowered).limit(1)
        ).first()
    else:
        existing = ctx.session.scalars(
            select(Commitment).where(Commitment.status == "open", func.lower(Commitment.title) == lowered).limit(1)
        ).first()
    if existing is not None:
        raise Refused(f"An open {kind} already has that title (id {existing.id}). Propose an edit or a note instead.")
    waiting = ctx.session.scalars(
        _pending()
        .where(AgentProposal.action == action, func.lower(AgentProposal.changes["title"].astext) == lowered)
        .limit(1)
    ).first()
    if waiting is not None:
        raise Refused(f"The same new {kind} is already waiting as a proposal.")


def _current(row: Task | Commitment, key: str) -> Any:
    value = getattr(row, key)
    return value.isoformat() if isinstance(value, date) else value


def _store(
    ctx: RunContext,
    action: str,
    kind: str,
    row: Task | Commitment | None,
    changes: dict,
    reason: str,
) -> dict:
    summary = summarise(action, changes, row)
    proposal = AgentProposal(
        run_id=ctx.run.id,
        origin=ctx.origin,
        rule=ctx.rule,
        label=ctx.label,
        action=action,
        ref_type=kind,
        ref_id=row.id if row is not None else None,
        changes=changes,
        summary=summary,
        reason=reason,
        ref_updated_at=row.updated_at if row is not None else None,
        status="pending",
        created_at=ctx.now,
    )
    ctx.session.add(proposal)
    # The session does not autoflush. Flush so the next duplicate check sees this one.
    ctx.session.flush()
    ctx.proposals.append(proposal)
    return {
        "ok": True,
        "proposal_id": str(proposal.id),
        "card": summary,
        "left_in_this_run": ctx.max_proposals - len(ctx.proposals),
    }


# --- the five functions ----------------------------------------------------


def get_state(ctx: RunContext, args: dict) -> dict:
    session = ctx.session
    state = ensure_system_state(session)
    today = ctx.today
    week_end = today + timedelta(days=6)
    task_open = Task.status != "done"

    def count(*where) -> int:
        return session.scalar(select(func.count()).select_from(Task).where(*where)) or 0

    counts = {
        "tasks_todo": count(Task.status == "todo"),
        "tasks_doing": count(Task.status == "doing"),
        "tasks_overdue": count(task_open, Task.due_on < today),
        "tasks_due_today": count(task_open, Task.due_on == today),
        "commitments_open": session.scalar(
            select(func.count()).select_from(Commitment).where(Commitment.status == "open")
        )
        or 0,
        "proposals_waiting": session.scalar(
            select(func.count()).select_from(AgentProposal).where(AgentProposal.status == "pending")
        )
        or 0,
    }
    load: dict[date, int] = {}
    for due_on, number in session.execute(
        select(Task.due_on, func.count()).where(task_open, Task.due_on.between(today, week_end)).group_by(Task.due_on)
    ):
        load[due_on] = load.get(due_on, 0) + number
    for due_on, number in session.execute(
        select(Commitment.due_on, func.count())
        .where(Commitment.status == "open", Commitment.due_on.between(today, week_end))
        .group_by(Commitment.due_on)
    ):
        load[due_on] = load.get(due_on, 0) + number
    days = [today + timedelta(days=offset) for offset in range(7)]
    local = ctx.local_now
    return {
        "ok": True,
        "house_time": local.isoformat(timespec="minutes"),
        "weekday": local.strftime("%A"),
        "house_date": today.isoformat(),
        "time_zone": ctx.tz_name,
        "paused": state.paused,
        "counts": counts,
        "next_7_days": [
            {"date": day.isoformat(), "weekday": day.strftime("%a"), "items": load.get(day, 0)} for day in days
        ],
    }


def search_items(ctx: RunContext, args: dict) -> dict:
    query: SearchArgs = _parse(SearchArgs, args)
    text = (query.text or "").strip()
    session = ctx.session
    items: list[dict] = []

    if query.kind in ("task", "any") and query.status in (None, "todo", "doing", "done"):
        statement = select(Task)
        if text:
            statement = statement.where(
                or_(Task.title.icontains(text, autoescape=True), Task.detail.icontains(text, autoescape=True))
            )
        if query.status:
            statement = statement.where(Task.status == query.status)
        if query.due_from:
            statement = statement.where(Task.due_on >= query.due_from)
        if query.due_to:
            statement = statement.where(Task.due_on <= query.due_to)
        statement = statement.order_by(
            case((Task.status == "done", 1), else_=0), Task.due_on.asc().nulls_last(), Task.title.asc()
        ).limit(query.limit)
        items += [_brief("task", row) for row in session.scalars(statement)]

    if query.kind in ("commitment", "any") and query.status in (None, "open", "kept", "dropped"):
        statement = select(Commitment)
        if text:
            statement = statement.where(
                or_(
                    Commitment.title.icontains(text, autoescape=True),
                    Commitment.detail.icontains(text, autoescape=True),
                )
            )
        if query.status:
            statement = statement.where(Commitment.status == query.status)
        if query.due_from:
            statement = statement.where(Commitment.due_on >= query.due_from)
        if query.due_to:
            statement = statement.where(Commitment.due_on <= query.due_to)
        statement = statement.order_by(
            case((Commitment.status == "open", 0), else_=1),
            Commitment.due_on.asc().nulls_last(),
            Commitment.title.asc(),
        ).limit(query.limit)
        items += [_brief("commitment", row) for row in session.scalars(statement)]

    items.sort(key=lambda item: (not _is_open(item), item["due_on"] or "9999-12-31", item["title"].lower()))
    items = items[: query.limit]
    return {"ok": True, "count": len(items), "items": items}


def get_item(ctx: RunContext, args: dict) -> dict:
    query: ItemArgs = _parse(ItemArgs, args)
    row = _load(ctx.session, query.kind, query.id)
    item = _brief(query.kind, row, detail_limit=None)
    item["owner"] = row.owner
    item["created_at"] = _iso(row.created_at)
    if query.kind == "commitment":
        item["source"] = row.source
    waiting = ctx.session.scalars(
        _pending().where(AgentProposal.ref_type == query.kind, AgentProposal.ref_id == row.id)
    ).all()
    return {
        "ok": True,
        "item": item,
        "waiting_proposals": [{"id": str(proposal.id), "summary": proposal.summary} for proposal in waiting],
    }


def propose_change(ctx: RunContext, args: dict) -> dict:
    query: ProposeArgs = _parse(ProposeArgs, args)
    _guard(ctx)
    reason = _reason(query.reason)
    action = query.action
    kind = "task" if action.endswith("_task") else "commitment"

    changes = {key: value for key, value in query.changes.items() if value is not None}
    if not changes:
        raise Refused("changes is empty. Name at least one field to set.")
    if "owner" in changes:
        raise Refused("The owner cannot be changed.")
    allowed = ALLOWED_FIELDS[action]
    unknown = sorted(set(changes) - allowed)
    if unknown:
        raise Refused(f"{action} takes only {', '.join(sorted(allowed))}. Not: {', '.join(unknown)}.")
    if isinstance(changes.get("detail"), str) and len(changes["detail"]) > PROPOSAL_DETAIL_LIMIT:
        raise Refused(f"detail is longer than {PROPOSAL_DETAIL_LIMIT} characters.")
    try:
        validated = _SCHEMAS[action].model_validate(changes)
    except ValidationError as exc:
        raise Refused(_first_error(exc)) from None
    clean: dict = validated.model_dump(mode="json", exclude_unset=True)

    due = clean.get("due_on")
    if due and date.fromisoformat(due) < ctx.today:
        raise Refused(f"due_on {due} is before today ({ctx.today.isoformat()}). Pick today or later.")

    if action.startswith("create_"):
        if query.id:
            raise Refused("Leave out id when creating.")
        _no_duplicate_create(ctx, action, kind, clean["title"])
        return _store(ctx, action, kind, None, clean, reason)

    if not query.id:
        raise Refused(f"id is required for {action}.")
    row = _load(ctx.session, kind, query.id)
    clean = {key: value for key, value in clean.items() if _current(row, key) != value}
    if not clean:
        raise Refused("That is already so. Nothing to propose.")
    _no_waiting_for_item(ctx, kind, row.id)
    return _store(ctx, action, kind, row, clean, reason)


def add_note(ctx: RunContext, args: dict) -> dict:
    query: NoteArgs = _parse(NoteArgs, args)
    _guard(ctx)
    reason = _reason(query.reason)
    note = " ".join(query.note.split())
    if not note:
        raise Refused("note is empty.")
    row = _load(ctx.session, query.kind, query.id)
    if row.detail and note.lower() in row.detail.lower():
        raise Refused("The item already says that.")
    if len(with_note(row.detail, note_line(ctx.today, note))) > DETAIL_LIMIT:
        raise Refused("The item's detail is full. Propose nothing.")
    _no_waiting_for_item(ctx, query.kind, row.id)
    return _store(ctx, "add_note", query.kind, row, {"note": note, "dated": ctx.today.isoformat()}, reason)


HANDLERS: dict[str, Callable[[RunContext, dict], dict]] = {
    "get_state": get_state,
    "search_items": search_items,
    "get_item": get_item,
    "propose_change": propose_change,
    "add_note": add_note,
}


def dispatch(ctx: RunContext, name: str, raw_arguments: Any) -> dict:
    handler = HANDLERS.get(name)
    if handler is None:
        return {"ok": False, "error": f"There is no function called {name!r}."}
    try:
        return handler(ctx, _arguments(raw_arguments))
    except Refused as exc:
        return {"ok": False, "error": str(exc)}
