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
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

_AGENT_TRIGGERS = "('feed', 'morning_review', 'doing_stalled', 'overdue_lingering', 'commitment_due_soon')"
# mistral-embed. A different model would need a new column and a migration.
MEMORY_EMBEDDING_DIM = 1024
_PROPOSAL_ACTIONS = (
    "'create_task', 'update_task', 'create_commitment', 'update_commitment', "
    "'add_note', 'create_shopping_item', 'remember', 'forget'"
)


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
    # Software switch. Keys still have to be set before the assistant runs.
    # Default on, so a house that already has keys stays on until someone turns it off.
    assistant_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class ReminderControl(Base):
    """House switch for local reminder cards. Off until someone turns it on.

    The row is not created by a boot patch. Alembic ``reminder_switch_off`` is
    the reviewable migration and is not applied from this process. ``create_all``
    on a fresh database creates the table with ``enabled`` false.
    """

    __tablename__ = "reminder_control"
    __table_args__ = (CheckConstraint("id = 1", name="ck_reminder_control_singleton"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
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
            f"action in ({_PROPOSAL_ACTIONS})",
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
    # How many memories were in the context that produced this card. Null on older rows.
    memories_used: Mapped[int | None] = mapped_column(Integer, nullable=True)


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
    fallback_used: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")


class ShoppingItem(Base):
    """A line on the house shopping list. A name and a tick. No allergen field."""

    __tablename__ = "shopping_items"
    __table_args__ = (
        CheckConstraint("char_length(name) > 0", name="ck_shopping_items_name"),
        Index("ix_shopping_items_ticked", "ticked"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    ticked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class CalendarSubscription(Base):
    """A read-only diary chosen in Settings. The provider id stays in this table."""

    __tablename__ = "calendar_subscriptions"
    __table_args__ = (
        UniqueConstraint("provider", "calendar_id", name="uq_calendar_subscriptions_calendar"),
        CheckConstraint("provider = 'google'", name="ck_calendar_subscriptions_provider"),
        CheckConstraint("char_length(display_name) > 0", name="ck_calendar_subscriptions_name"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    provider: Mapped[str] = mapped_column(String(16), nullable=False, default="google", server_default="google")
    calendar_id: Mapped[str] = mapped_column(String(200), nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class CommuteShift(Base):
    """One rota commute. The only stored facts are start, end, and ``Wembley``.

    The id is the row key. Nothing else from the push is kept: no name, no
    staff id, and no journey.
    """

    __tablename__ = "commute_shifts"
    __table_args__ = (
        CheckConstraint("location_label = 'Wembley'", name="ck_commute_shifts_label"),
        CheckConstraint("end_at > start_at", name="ck_commute_shifts_order"),
        Index("ix_commute_shifts_start", "start_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    location_label: Mapped[str] = mapped_column(String(40), nullable=False)


class MemoryItem(Base):
    """One household memory. The assistant proposes it. Apply is what saves it.

    ``source`` records how it arrived. ``forget`` is allowed by the check and is
    not used for a stored row: forget deletes. The embedding is mistral-embed
    when that call works, and null when it does not. Retrieval then uses words.
    """

    __tablename__ = "memory_items"
    __table_args__ = (
        CheckConstraint("kind in ('preference', 'fact', 'routine')", name="ck_memory_items_kind"),
        CheckConstraint(
            "source in ('remember', 'forget', 'smart-add', 'manual')",
            name="ck_memory_items_source",
        ),
        CheckConstraint("char_length(text) > 0", name="ck_memory_items_text"),
        Index("ix_memory_items_pinned", "pinned"),
        Index(
            "ix_memory_items_embedding",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    text: Mapped[str] = mapped_column(String(400), nullable=False)
    source: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    pinned: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    embedding: Mapped[list[float] | None] = mapped_column(Vector(MEMORY_EMBEDDING_DIM), nullable=True)


class AlertDismissal(Base):
    """One dismissed alert incident. The signature changes when the incident does.

    This row does not send anything. It only hides that card.
    """

    __tablename__ = "alert_dismissals"
    __table_args__ = (
        CheckConstraint(
            "kind in ('mistral_failing', 'activity_poll', 'database_error')",
            name="ck_alert_dismissals_kind",
        ),
    )

    kind: Mapped[str] = mapped_column(String(32), primary_key=True)
    signature: Mapped[str] = mapped_column(String(80), nullable=False)
    dismissed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class IntegrationStatus(Base):
    """Last outcome of a connection. A class name only: no body, postcode, or token."""

    __tablename__ = "integration_status"
    __table_args__ = (CheckConstraint("name in ('weather', 'diary')", name="ck_integration_status_name"),)

    name: Mapped[str] = mapped_column(String(32), primary_key=True)
    last_ok_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error_class: Mapped[str | None] = mapped_column(String(40), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class XConnection(Base):
    """Nick's X account. The tokens are Fernet ciphertext, never the raw values."""

    __tablename__ = "x_connection"
    __table_args__ = (CheckConstraint("id = 1", name="ck_x_connection_singleton"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    x_user_id: Mapped[str] = mapped_column(String(32), nullable=False)
    username: Mapped[str] = mapped_column(String(15), nullable=False)
    access_token: Mapped[str] = mapped_column(Text, nullable=False)
    refresh_token: Mapped[str] = mapped_column(Text, nullable=False)
    access_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    scopes: Mapped[str] = mapped_column(String(200), nullable=False)
    connected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class XOauthPending(Base):
    """One PKCE attempt. The verifier is ciphertext. The row is single use."""

    __tablename__ = "x_oauth_pending"

    state: Mapped[str] = mapped_column(String(80), primary_key=True)
    verifier: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class XWatch(Base):
    """An account or a keyword Nick asked to watch. Recent search reads it."""

    __tablename__ = "x_watches"
    __table_args__ = (
        UniqueConstraint("kind", "value", name="uq_x_watches_value"),
        CheckConstraint("kind in ('account', 'keyword')", name="ck_x_watches_kind"),
        CheckConstraint("char_length(value) > 0", name="ck_x_watches_value"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    value: Mapped[str] = mapped_column(String(80), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class XItem(Base):
    """A bookmark, a watch match, or a draft. A draft is not posted until confirmed."""

    __tablename__ = "x_items"
    __table_args__ = (
        UniqueConstraint("kind", "external_id", name="uq_x_items_external"),
        CheckConstraint("kind in ('bookmark', 'watch_match', 'draft')", name="ck_x_items_kind"),
        CheckConstraint(
            "status in ('pending', 'applied', 'dismissed', 'posted', 'expired')",
            name="ck_x_items_status",
        ),
        CheckConstraint("source in ('poll', 'webhook', 'assistant')", name="ck_x_items_source"),
        CheckConstraint("char_length(text) > 0", name="ck_x_items_text"),
        Index("ix_x_items_status", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    external_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    author: Mapped[str | None] = mapped_column(String(15), nullable=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    url: Mapped[str | None] = mapped_column(String(300), nullable=True)
    reason: Mapped[str | None] = mapped_column(String(300), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending", server_default="pending")
    source: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    posted_tweet_id: Mapped[str | None] = mapped_column(String(32), nullable=True)


class XCursor(Base):
    """The newest id already seen, so the next poll does not re-read it."""

    __tablename__ = "x_cursors"

    name: Mapped[str] = mapped_column(String(80), primary_key=True)
    since_id: Mapped[str] = mapped_column(String(32), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class XMeter(Base):
    """Last credits and rate headers. No tweet text and no token."""

    __tablename__ = "x_meter"
    __table_args__ = (CheckConstraint("id = 1", name="ck_x_meter_singleton"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    credits_remaining: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rate_remaining: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rate_reset_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    backoff_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_poll_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error_class: Mapped[str | None] = mapped_column(String(40), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class XPostAudit(Base):
    """One attempt to post a draft. The tweet id is kept. The token is not."""

    __tablename__ = "x_post_audit"
    __table_args__ = (
        CheckConstraint("outcome in ('posted', 'failed')", name="ck_x_post_audit_outcome"),
        Index("ix_x_post_audit_item", "item_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    item_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("x_items.id"), nullable=False)
    outcome: Mapped[str] = mapped_column(String(16), nullable=False)
    tweet_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    error_class: Mapped[str | None] = mapped_column(String(40), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
