from datetime import date, datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from organiser.domain import (
    ActionMode,
    ActionStatus,
    CommitmentStatus,
    EventKind,
    Priority,
    TaskStatus,
)


def _strip_strings(value: Any) -> Any:
    if isinstance(value, str):
        return value.strip()
    return value


class APIModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    @field_validator("*", mode="before")
    @classmethod
    def strip_strings(cls, value: Any) -> Any:
        return _strip_strings(value)


class TaskCreate(APIModel):
    title: str = Field(min_length=1, max_length=200)
    detail: str | None = Field(default=None, max_length=4000)
    due_on: date | None = None
    priority: Priority = Priority.medium
    status: TaskStatus = TaskStatus.todo
    owner: str = Field(default="Nick", min_length=1, max_length=80)


class TaskUpdate(APIModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    detail: str | None = Field(default=None, max_length=4000)
    due_on: date | None = None
    priority: Priority | None = None
    status: TaskStatus | None = None
    owner: str | None = Field(default=None, min_length=1, max_length=80)


class TaskRead(APIModel):
    id: UUID
    title: str
    detail: str | None
    due_on: date | None
    priority: Priority
    status: TaskStatus
    owner: str
    created_at: datetime
    updated_at: datetime


class TaskList(APIModel):
    items: list[TaskRead]


class CommitmentCreate(APIModel):
    title: str = Field(min_length=1, max_length=200)
    detail: str | None = Field(default=None, max_length=4000)
    due_on: date | None = None
    status: CommitmentStatus = CommitmentStatus.open
    owner: str = Field(default="Nick", min_length=1, max_length=80)
    source: str = Field(default="manual", min_length=1, max_length=32)


class CommitmentUpdate(APIModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    detail: str | None = Field(default=None, max_length=4000)
    due_on: date | None = None
    status: CommitmentStatus | None = None
    owner: str | None = Field(default=None, min_length=1, max_length=80)
    source: str | None = Field(default=None, min_length=1, max_length=32)


class CommitmentRead(APIModel):
    id: UUID
    title: str
    detail: str | None
    due_on: date | None
    status: CommitmentStatus
    owner: str
    source: str
    created_at: datetime
    updated_at: datetime


class CommitmentList(APIModel):
    items: list[CommitmentRead]


class EventCreate(APIModel):
    kind: EventKind
    title: str = Field(min_length=1, max_length=200)
    body: str | None = Field(default=None, max_length=4000)
    owner: str | None = Field(default=None, min_length=1, max_length=80)
    recorded_at: datetime | None = None


class EventUpdate(APIModel):
    kind: EventKind | None = None
    title: str | None = Field(default=None, min_length=1, max_length=200)
    body: str | None = Field(default=None, max_length=4000)
    owner: str | None = Field(default=None, min_length=1, max_length=80)
    recorded_at: datetime | None = None


class EventRead(APIModel):
    id: UUID
    kind: EventKind
    title: str
    body: str | None
    owner: str | None
    recorded_at: datetime
    created_at: datetime
    updated_at: datetime


class EventList(APIModel):
    items: list[EventRead]


class ActionRequestCreate(APIModel):
    title: str = Field(min_length=1, max_length=200)
    detail: str | None = Field(default=None, max_length=4000)
    mode: ActionMode
    status: ActionStatus = ActionStatus.pending
    owner: str = Field(default="Nick", min_length=1, max_length=80)


class ActionRequestUpdate(APIModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    detail: str | None = Field(default=None, max_length=4000)
    mode: ActionMode | None = None
    status: ActionStatus | None = None
    owner: str | None = Field(default=None, min_length=1, max_length=80)


class ActionRequestRead(APIModel):
    id: UUID
    title: str
    detail: str | None
    mode: ActionMode
    status: ActionStatus
    owner: str
    resolution: str | None
    decided_at: datetime | None
    effect_applied: bool
    created_at: datetime
    updated_at: datetime


class ActionRequestList(APIModel):
    items: list[ActionRequestRead]


class EffectResult(APIModel):
    applied: bool
    summary: str


class ApprovalDecision(ActionRequestRead):
    effect: EffectResult


class BriefItem(APIModel):
    id: UUID | None = None
    title: str
    detail: str | None = None
    meta: str | None = None


class BriefSection(APIModel):
    key: str
    title: str
    placeholder: bool = False
    summary: str
    items: list[BriefItem]


class MorningBrief(APIModel):
    title: str
    as_of: datetime
    house_date: date
    paused: bool
    note: str | None = None
    sections: list[BriefSection]


class SystemRead(APIModel):
    paused: bool
    activity: str
    status_text: str
    house_date: date
    updated_at: datetime


def apply_changes(row: object, payload: BaseModel) -> None:
    from organiser.timeutil import utcnow

    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        if isinstance(value, Enum):
            value = value.value
        setattr(row, key, value)
    if hasattr(row, "updated_at"):
        row.updated_at = utcnow()
