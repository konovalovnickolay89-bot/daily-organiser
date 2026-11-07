from datetime import date, datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from organiser.domain import (
    ActionMode,
    ActionStatus,
    AgentTrigger,
    CommitmentStatus,
    EventKind,
    GreetingReason,
    Priority,
    ProposalAction,
    ProposalStatus,
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
    # Stable key for a diary row. Not a provider id.
    ref: str | None = None
    ticked: bool | None = None


class BriefSection(APIModel):
    key: str
    title: str
    placeholder: bool = False
    summary: str
    items: list[BriefItem]
    footnote: str | None = None


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
    greeting: str
    greeting_reason: GreetingReason
    arrived_at: datetime | None = None
    debounce_until: datetime | None = None
    playlist: bool = False


class HouseFacts(APIModel):
    """Settings card. Configured or not. Never a secret, coordinate, postcode, or calendar id."""

    timezone: str
    # Effective: keys are set and the switch is on.
    assistant: str
    # The persisted switch, even when a key is missing.
    assistant_switch: str
    runs_left_today: int
    diary: str
    weather_location: str
    tfl: str
    banto: str
    # on when VOICE_INPUT_ENABLED. The mic stays hidden otherwise.
    voice_input: str


class AssistantSwitch(BaseModel):
    """The Settings switch. Extra fields are refused."""

    model_config = ConfigDict(extra="forbid")
    enabled: bool


class ShoppingCreate(APIModel):
    """A shop line. Names only. An allergen field is rejected."""

    model_config = ConfigDict(from_attributes=True, extra="forbid")
    name: str = Field(min_length=1, max_length=80)


class ShoppingRead(APIModel):
    id: UUID
    name: str
    ticked: bool
    created_at: datetime
    updated_at: datetime


class ShoppingList(APIModel):
    items: list[ShoppingRead]


class CalendarEntry(APIModel):
    """A diary name. The provider id is not on this card."""

    id: UUID | None = None
    name: str
    enabled: bool = True


class CalendarListRead(APIModel):
    configured: bool
    using_primary: bool
    items: list[CalendarEntry]


class CalendarName(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=200)


class FeedRequest(APIModel):
    text: str = Field(min_length=1, max_length=1000)


class ProposalIngest(APIModel):
    """One task card from a curator. Apply creates it. This request does not."""

    title: str = Field(min_length=1, max_length=200)
    due_on: date | None = None
    reason: str | None = Field(default=None, max_length=300)
    source: str | None = Field(default=None, max_length=80)


class ActivityItem(APIModel):
    id: UUID
    at: datetime
    text: str
    type: str


class ActivityList(APIModel):
    items: list[ActivityItem]


class ReviewRequest(APIModel):
    trigger: AgentTrigger
    window_key: str = Field(min_length=1, max_length=160)


class MemoryMatch(APIModel):
    id: UUID
    kind: str
    text: str


class ProposalRead(APIModel):
    id: UUID
    origin: str
    rule: AgentTrigger
    label: str
    action: ProposalAction
    ref_type: str | None
    ref_id: UUID | None
    summary: str
    reason: str
    status: ProposalStatus
    created_at: datetime
    decided_at: datetime | None
    applied_ref_id: UUID | None
    date_note: str | None = None
    memories_used: int | None = None
    matches: list[MemoryMatch] = Field(default_factory=list)


class ApplySelection(BaseModel):
    """Optional confirm list for a forget card. Other cards ignore it."""

    model_config = ConfigDict(extra="ignore")
    memory_ids: list[UUID] | None = None


class MemoryCreate(APIModel):
    kind: str = "fact"
    text: str = Field(min_length=1, max_length=400)

    @field_validator("kind")
    @classmethod
    def _kind(cls, value: str) -> str:
        if value not in ("preference", "fact", "routine"):
            raise ValueError("Kind must be preference, fact, or routine.")
        return value


class MemoryPin(APIModel):
    pinned: bool


class MemoryRead(APIModel):
    id: UUID
    kind: str
    text: str
    source: str
    created_at: datetime
    last_used_at: datetime | None
    pinned: bool


class MemoryList(APIModel):
    items: list[MemoryRead]


class MemoryExport(APIModel):
    exported_at: datetime
    items: list[MemoryRead]


class MemorySearch(APIModel):
    """Ranked memories. ``mode`` is ``hybrid`` when an embedding was used, else ``fts``."""

    mode: str
    items: list[MemoryRead]


class PlaylistSetting(APIModel):
    enabled: bool
    available: bool
    source: str
    profile: str
    detail: str


class AlertsSetting(APIModel):
    enabled: bool


class WebhooksSetting(APIModel):
    enabled: bool
    banto: str
    banto_x: str


class VoiceSetting(APIModel):
    mic: str
    env_enabled: bool
    voxtral: str
    detail: str


class XLimitsSetting(APIModel):
    enabled: bool
    sync_minutes: int
    daily_cap: int
    from_max: int
    draft_expiry_days: int
    detail: str


class AgentContextSetting(APIModel):
    token_budget: int
    memory_limit: int
    smart_add_days: int
    catch_up_days: int


class DocsStatus(APIModel):
    state: str
    detail: str


class FeatureSettings(APIModel):
    """Every house choice on Settings. No secret, postcode, coordinate, or token."""

    playlist: PlaylistSetting
    alerts: AlertsSetting
    webhooks: WebhooksSetting
    voice: VoiceSetting
    x: XLimitsSetting
    agent_context: AgentContextSetting
    docs: DocsStatus


class FeatureSettingsPatch(BaseModel):
    """A partial save. Extra fields, including ``x_enabled``, are refused."""

    model_config = ConfigDict(extra="forbid")
    playlist_enabled: bool | None = None
    alerts_enabled: bool | None = None
    webhooks_enabled: bool | None = None
    voice_enabled: bool | None = None
    x_sync_minutes: int | None = Field(default=None, ge=5, le=1440)
    x_daily_cap: int | None = Field(default=None, ge=1, le=100)
    x_from_max: int | None = Field(default=None, ge=1, le=20)
    x_draft_expiry_days: int | None = Field(default=None, ge=1, le=30)
    context_token_budget: int | None = Field(default=None, ge=500, le=8000)
    context_memory_limit: int | None = Field(default=None, ge=1, le=10)
    context_smart_add_days: int | None = Field(default=None, ge=1, le=14)
    context_catch_up_days: int | None = Field(default=None, ge=1, le=14)


class DueRead(APIModel):
    trigger: AgentTrigger
    window_key: str
    label: str


class LastReply(APIModel):
    text: str
    at: datetime
    trigger: AgentTrigger


class AgentState(APIModel):
    enabled: bool
    paused: bool
    reachable: bool
    as_of: datetime
    house_date: date
    due: DueRead | None
    runs_left_today: int
    proactive_left_today: int
    last_reply: LastReply | None
    proposals: list[ProposalRead]


class AgentResult(APIModel):
    run_id: UUID
    trigger: AgentTrigger
    reply: str | None
    searched: bool
    proposals: list[ProposalRead]


class AppliedChange(APIModel):
    ref_type: str
    ref_id: UUID
    summary: str


class ApplyResult(APIModel):
    proposal: ProposalRead
    applied: AppliedChange


class CatchUpItemRead(APIModel):
    id: UUID
    rule: str
    label: str
    summary: str
    reason: str
    ref_type: str
    ref_id: UUID
    status: str
    fallback_used: bool = False


class ShiftPush(BaseModel):
    """A rota shift. Extra fields are refused. The label ``Wembley`` is the only one kept."""

    model_config = ConfigDict(extra="forbid")
    start: datetime
    end: datetime
    location_label: str = Field(min_length=1, max_length=40)

    @field_validator("location_label")
    @classmethod
    def _one_line(cls, value: str) -> str:
        return " ".join(value.split())


class ShiftRead(APIModel):
    id: UUID
    start: datetime
    end: datetime
    location_label: str


class CatchUpRead(APIModel):
    paused: bool
    quiet: bool
    as_of: datetime
    house_date: date
    items: list[CatchUpItemRead]


class XMeterRead(APIModel):
    """Credits and rate for the status line. No token and no tweet text."""

    enabled: bool = False
    connected: bool = False
    credits_remaining: int | None = None
    rate_remaining: int | None = None
    backing_off: bool = False
    attention: str | None = None


class ServiceHealth(APIModel):
    """One connection, by name. The detail is a class or a short line, never a secret."""

    name: str
    state: str
    detail: str


class StatusRead(APIModel):
    """Settings status. Times are instants. The database size is bytes. No house text."""

    health: str
    version: str
    last_mistral_success: datetime | None = None
    last_activity_poll: datetime | None = None
    database_bytes: int | None = None
    x: XMeterRead = XMeterRead()
    services: list[ServiceHealth] = Field(default_factory=list)


class XWatchRead(APIModel):
    id: UUID
    kind: str
    value: str


class XStatusRead(APIModel):
    enabled: bool
    configured: bool
    connected: bool
    username: str | None = None
    watches: list[XWatchRead] = []


class XWatchWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: str
    value: str = Field(min_length=1, max_length=80)


class XConnectRead(APIModel):
    authorize_url: str


class XCardRead(APIModel):
    id: UUID
    kind: str
    summary: str
    detail: str | None = None
    url: str | None = None
    expires_at: datetime | None = None


class XCardList(APIModel):
    enabled: bool
    items: list[XCardRead]


class XPollRead(APIModel):
    ran: bool
    reason: str


class XPostWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    confirm: bool = False


class XDecisionRead(APIModel):
    id: UUID
    status: str
    tweet_id: str | None = None


class PlaylistRead(APIModel):
    shown: bool
    offline: bool = False
    title: str | None = None
    genre: str | None = None
    artwork_url: str | None = None
    permalink_url: str | None = None


class AlertRead(APIModel):
    kind: str
    title: str
    detail: str


class AlertList(APIModel):
    items: list[AlertRead]


class CatchUpApplyResult(APIModel):
    item: CatchUpItemRead
    applied: AppliedChange


def apply_changes(row: object, payload: BaseModel) -> None:
    from organiser.timeutil import utcnow

    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        if isinstance(value, Enum):
            value = value.value
        setattr(row, key, value)
    if hasattr(row, "updated_at"):
        row.updated_at = utcnow()
