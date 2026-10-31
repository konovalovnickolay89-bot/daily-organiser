"""Request and response bodies."""

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from organiser.tags import clean_tags

Priority = Literal["low", "medium", "high"]
Status = Literal["todo", "doing", "done"]
AssistMode = Literal["off", "when_useful"]
Source = Literal["manual", "bot"]


def _clean_title(value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("Title is required")
    return value


def _clean_body(value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("Note text is required")
    return value


def _clean_hint(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None


class LoginIn(BaseModel):
    password: str = Field(min_length=1, max_length=1024)


class OkOut(BaseModel):
    ok: bool = True


class MeOut(BaseModel):
    authenticated: bool


class HealthOut(BaseModel):
    ok: bool = True


class TaskIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    due_date: date | None = None
    priority: Priority = "medium"
    status: Status = "todo"
    recurring: bool = False
    assist_mode: AssistMode = "when_useful"
    context_hint: str | None = Field(default=None, max_length=300)
    source: Source = "manual"

    @field_validator("title")
    @classmethod
    def title_not_blank(cls, value: str) -> str:
        return _clean_title(value)

    @field_validator("context_hint")
    @classmethod
    def hint_blank_is_absent(cls, value: str | None) -> str | None:
        return _clean_hint(value)


class TaskPatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    due_date: date | None = None
    priority: Priority | None = None
    status: Status | None = None
    recurring: bool | None = None
    assist_mode: AssistMode | None = None
    context_hint: str | None = Field(default=None, max_length=300)
    source: Source | None = None

    @field_validator("title")
    @classmethod
    def title_not_blank(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _clean_title(value)

    @field_validator("context_hint")
    @classmethod
    def hint_blank_is_absent(cls, value: str | None) -> str | None:
        return _clean_hint(value)


class TaskOut(BaseModel):
    id: int
    title: str
    due_date: date | None
    priority: Priority
    status: Status
    recurring: bool
    assist_mode: AssistMode
    context_hint: str | None = None
    source: Source
    created_at: str
    updated_at: str


class NoteIn(BaseModel):
    body: str = Field(min_length=1, max_length=20_000)
    tags: list[str] = []
    task_id: int | None = None
    source: Source = "manual"

    @field_validator("body")
    @classmethod
    def body_not_blank(cls, value: str) -> str:
        return _clean_body(value)

    @field_validator("tags")
    @classmethod
    def normalise_tags(cls, value: list[str]) -> list[str]:
        return clean_tags(value)


class NotePatch(BaseModel):
    body: str | None = Field(default=None, min_length=1, max_length=20_000)
    tags: list[str] | None = None
    task_id: int | None = None
    source: Source | None = None

    @field_validator("body")
    @classmethod
    def body_not_blank(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _clean_body(value)

    @field_validator("tags")
    @classmethod
    def normalise_tags(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        return clean_tags(value)


class NoteOut(BaseModel):
    id: int
    body: str
    tags: list[str]
    task_id: int | None
    task_title: str | None
    source: Source
    created_at: str
    updated_at: str


class TodayOut(BaseModel):
    date: date
    tasks: list[TaskOut]
    notes: list[NoteOut]
