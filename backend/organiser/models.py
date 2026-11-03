import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

_AGENT_TRIGGERS = "('feed', 'morning_review', 'doing_stalled', 'overdue_lingering', 'commitment_due_soon')"


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
    # Last accepted arrival. Null until the house posts one. The presence bar
    # shows "Welcome home" only while this sits inside the one-hour window.
    arrived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Last time the arrival screen recorded a look. Catch-up measures the gap
    # from here. A paused house does not move it.
    last_looked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class AgentRun(Base):
    """One run of the Mistral assistant. The house keeps what went in and what came back.

    ``(trigger, window_key)`` is unique, so a proactive review runs once per
    window even with two screens open. Times come from the house clock, not
    from Postgres, so the daily caps follow the frozen clock in tests.
    """

    __tablename__ = "agent_runs"
    __table_args__ = (
        CheckConstraint(f"trigger in {_AGENT_TRIGGERS}", name="ck_agent_runs_trigger"),
        CheckConstraint("status in ('running', 'done', 'failed')", name="ck_agent_runs_status"),
        UniqueConstraint("trigger", "window_key", name="uq_agent_runs_window"),
        Index("ix_agent_runs_started_at", "started_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    trigger: Mapped[str] = mapped_column(String(32), nullable=False)
    window_key: Mapped[str] = mapped_column(String(160), nullable=False)
    input_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    reply: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="running", server_default="running")
    searched: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    error: Mapped[str | None] = mapped_column(String(200), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AgentProposal(Base):
    """A change the assistant proposed. Nothing happens until Nick taps Apply.

    Apply makes exactly ``changes`` to the named row, inside this database.
    ``ref_updated_at`` is the row's stamp when proposed: if the row moved since,
    Apply refuses and the proposal turns ``stale``.

    ``origin`` ``ingest`` is a card from ``POST /agent/proposals``. It has no
    Mistral run, so ``run_id`` is null. Apply still uses the same allowlist.
    """

    __tablename__ = "agent_proposals"
    __table_args__ = (
        CheckConstraint("origin in ('feed', 'proactive', 'ingest')", name="ck_agent_proposals_origin"),
        CheckConstraint(f"rule in {_AGENT_TRIGGERS}", name="ck_agent_proposals_rule"),
        CheckConstraint(
            "action in ('create_task', 'update_task', 'create_commitment', 'update_commitment', 'add_note')",
            name="ck_agent_proposals_action",
        ),
        CheckConstraint(
            "ref_type is null or ref_type in ('task', 'commitment')",
            name="ck_agent_proposals_ref_type",
        ),
        CheckConstraint(
            "status in ('pending', 'applied', 'dismissed', 'stale')",
            name="ck_agent_proposals_status",
        ),
        Index("ix_agent_proposals_status", "status"),
        Index("ix_agent_proposals_ref", "ref_type", "ref_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("agent_runs.id"), nullable=True)
    origin: Mapped[str] = mapped_column(String(16), nullable=False)
    rule: Mapped[str] = mapped_column(String(32), nullable=False)
    label: Mapped[str] = mapped_column(String(80), nullable=False)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    ref_type: Mapped[str | None] = mapped_column(String(16), nullable=True)
    ref_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    changes: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    summary: Mapped[str] = mapped_column(String(240), nullable=False)
    reason: Mapped[str] = mapped_column(String(300), nullable=False)
    ref_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending", server_default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    applied_ref_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)


_CATCHUP_RULES = "('overdue', 'due_today', 'stalled', 'commitment_due', 'brief')"


class CatchUpPass(Base):
    """One catch-up after a gap. ``window_key`` is that gap, so two screens share it."""

    __tablename__ = "catchup_passes"
    __table_args__ = (UniqueConstraint("window_key", name="uq_catchup_passes_window"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    window_key: Mapped[str] = mapped_column(String(160), nullable=False)
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    from_looked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class CatchUpItem(Base):
    """One card in a catch-up. Apply adds the stored note; nothing else changes.

    Not now sets ``dismissed`` and the item rests. ``position`` is the order
    the rules chose, most pressing first.
    """

    __tablename__ = "catchup_items"
    __table_args__ = (
        CheckConstraint(f"rule in {_CATCHUP_RULES}", name="ck_catchup_items_rule"),
        CheckConstraint("action = 'add_note'", name="ck_catchup_items_action"),
        CheckConstraint("ref_type in ('task', 'commitment')", name="ck_catchup_items_ref_type"),
        CheckConstraint(
            "status in ('pending', 'applied', 'dismissed', 'stale')",
            name="ck_catchup_items_status",
        ),
        Index("ix_catchup_items_status", "status"),
        Index("ix_catchup_items_ref", "ref_type", "ref_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    pass_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("catchup_passes.id"), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    rule: Mapped[str] = mapped_column(String(32), nullable=False)
    label: Mapped[str] = mapped_column(String(80), nullable=False)
    action: Mapped[str] = mapped_column(String(32), nullable=False, default="add_note", server_default="add_note")
    ref_type: Mapped[str] = mapped_column(String(16), nullable=False)
    ref_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    changes: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    summary: Mapped[str] = mapped_column(String(240), nullable=False)
    reason: Mapped[str] = mapped_column(String(300), nullable=False)
    ref_updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending", server_default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
