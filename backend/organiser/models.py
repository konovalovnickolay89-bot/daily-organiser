import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Index,
    Integer,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Task(Base):
    """A household task. Owner and status are required."""

    __tablename__ = "tasks"
    __table_args__ = (
        CheckConstraint("status in ('todo', 'doing', 'done')", name="ck_tasks_status"),
        CheckConstraint("priority in ('low', 'medium', 'high')", name="ck_tasks_priority"),
        CheckConstraint("char_length(owner) > 0", name="ck_tasks_owner"),
        Index("ix_tasks_due_status", "due_on", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    due_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    priority: Mapped[str] = mapped_column(String(16), nullable=False, default="medium", server_default="medium")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="todo", server_default="todo")
    owner: Mapped[str] = mapped_column(String(80), nullable=False, default="Nick", server_default="Nick")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class Commitment(Base):
    """Something the household has already taken on."""

    __tablename__ = "commitments"
    __table_args__ = (
        CheckConstraint("status in ('open', 'kept', 'dropped')", name="ck_commitments_status"),
        CheckConstraint("char_length(owner) > 0", name="ck_commitments_owner"),
        Index("ix_commitments_status", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    due_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="open", server_default="open")
    owner: Mapped[str] = mapped_column(String(80), nullable=False, default="Nick", server_default="Nick")
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="manual", server_default="manual")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class Event(Base):
    """Operational log. Events are memory, not a workflow, so they have no status."""

    __tablename__ = "events"
    __table_args__ = (
        CheckConstraint(
            "kind in ('note', 'system', 'approval', 'task', 'commitment', 'brief')",
            name="ck_events_kind",
        ),
        Index("ix_events_recorded_at", "recorded_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    owner: Mapped[str | None] = mapped_column(String(80), nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class ActionRequest(Base):
    """A decision waiting on someone at home.

    ``effect_applied`` is constrained to false. Approve and skip change status only.
    Observe, advise, and prepare are stubs. Execute is stored so the decision can be
    recorded, and it is not wired to any outside action.
    """

    __tablename__ = "action_requests"
    __table_args__ = (
        CheckConstraint("mode in ('observe', 'advise', 'prepare', 'execute')", name="ck_action_requests_mode"),
        CheckConstraint(
            "status in ('pending', 'approved', 'skipped')",
            name="ck_action_requests_status",
        ),
        CheckConstraint("effect_applied = false", name="ck_action_requests_no_effect"),
        CheckConstraint("char_length(owner) > 0", name="ck_action_requests_owner"),
        Index("ix_action_requests_status", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    mode: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending", server_default="pending")
    owner: Mapped[str] = mapped_column(String(80), nullable=False, default="Nick", server_default="Nick")
    resolution: Mapped[str | None] = mapped_column(Text, nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    effect_applied: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class SystemState(Base):
    """Single row for the presence bar."""

    __tablename__ = "system_state"
    __table_args__ = (
        CheckConstraint("id = 1", name="ck_system_state_singleton"),
        CheckConstraint("activity in ('quiet', 'paused')", name="ck_system_state_activity"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    paused: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    activity: Mapped[str] = mapped_column(String(32), nullable=False, default="quiet", server_default="quiet")
    status_text: Mapped[str] = mapped_column(String(160), nullable=False, default="All quiet", server_default="All quiet")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
