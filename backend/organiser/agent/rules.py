"""When the assistant may speak without being asked.

The rules are fixed here. Mistral only words a run once a rule says it is due.
``proactive_due`` is pure: the reads that feed it live in ``build_snapshot``.

    morning_review       first screen read 06:00-10:59, once per house day, up to 2 proposals
    doing_stalled        task in progress, no update for 3+ days, 1 proposal
    overdue_lingering    task not done, due 2+ days ago, 1 proposal
    commitment_due_soon  open commitment due today or tomorrow, 1 proposal

Always: nothing while paused, nothing proactive 22:00-05:59, at most
``agent_proactive_per_day`` proposals a day, one proactive card at a time.
Not now hides an item for 72 hours. After a second look at the same item
(for the same rule) nothing more is said until the item itself changes.
"""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from organiser.config import Settings
from organiser.models import AgentProposal, AgentRun, Commitment, Task
from organiser.services.system import ensure_system_state

STALLED_DAYS = 3
OVERDUE_DAYS = 2
COOLDOWN = timedelta(hours=72)
LOOKS_PER_CHANGE = 2
PROACTIVE_HOURS = (6, 22)
MORNING_HOURS = (6, 11)
FEED_PROPOSALS = 3
MORNING_REVIEW_PROPOSALS = 2
STALE_PROPOSALS = 1
STALE_RULES = ("doing_stalled", "overdue_lingering", "commitment_due_soon")
HISTORY = timedelta(days=60)

FEED_LABEL = "From your note"
MORNING_LABEL = "Morning review"

_UTC = ZoneInfo("UTC")


@dataclass(frozen=True)
class Candidate:
    rule: str
    ref_type: str
    ref_id: UUID
    title: str
    status: str
    due_on: date | None
    ref_updated_at: datetime
    reason: str
    look: int = 1

    @property
    def base_key(self) -> str:
        return window_base(self.ref_type, self.ref_id, self.ref_updated_at)

    @property
    def window_key(self) -> str:
        return f"{self.base_key}#{self.look}"


@dataclass(frozen=True)
class Snapshot:
    enabled: bool
    paused: bool
    runs_today: int
    proactive_today: int
    proactive_pending: bool
    morning_claimed: bool
    candidates: tuple[Candidate, ...] = ()


@dataclass(frozen=True)
class Due:
    trigger: str
    window_key: str
    label: str
    max_proposals: int
    candidate: Candidate | None = None


def window_base(ref_type: str, ref_id: UUID, updated_at: datetime) -> str:
    """One item at one version. A new edit gives a new base, so the item can be looked at again."""
    return f"{ref_type}:{ref_id}:{updated_at.astimezone(_UTC).isoformat()}"


def in_hours(local: datetime, hours: tuple[int, int]) -> bool:
    return hours[0] <= local.hour < hours[1]


def proactive_due(
    local_now: datetime,
    snapshot: Snapshot,
    *,
    runs_per_day: int,
    proactive_per_day: int,
) -> Due | None:
    """The one review the screen may ask for now, or None."""
    if not snapshot.enabled or snapshot.paused:
        return None
    if not in_hours(local_now, PROACTIVE_HOURS):
        return None
    if snapshot.runs_today >= runs_per_day:
        return None
    left = proactive_per_day - snapshot.proactive_today
    if left <= 0 or snapshot.proactive_pending:
        return None
    if in_hours(local_now, MORNING_HOURS) and not snapshot.morning_claimed:
        return Due(
            trigger="morning_review",
            window_key=local_now.date().isoformat(),
            label=MORNING_LABEL,
            max_proposals=min(MORNING_REVIEW_PROPOSALS, left),
        )
    if snapshot.candidates:
        candidate = snapshot.candidates[0]
        return Due(
            trigger=candidate.rule,
            window_key=candidate.window_key,
            label=candidate.reason,
            max_proposals=min(STALE_PROPOSALS, left),
            candidate=candidate,
        )
    return None


def stale_reason(rule: str, local_now: datetime, row: Task | Commitment) -> str | None:
    """Why ``rule`` fires for ``row`` now, or None. These strings become the card label."""
    today = local_now.date()
    if rule == "doing_stalled":
        if row.status != "doing":
            return None
        days = (local_now - row.updated_at).days
        return f"In progress, no update for {days} days" if days >= STALLED_DAYS else None
    if rule == "overdue_lingering":
        if row.status == "done" or row.due_on is None:
            return None
        days = (today - row.due_on).days
        return f"{days} days overdue" if days >= OVERDUE_DAYS else None
    if rule == "commitment_due_soon":
        if row.status != "open" or row.due_on is None:
            return None
        if row.due_on == today:
            return "Due today"
        if row.due_on == today + timedelta(days=1):
            return "Due tomorrow"
        return None
    raise ValueError(f"Unknown rule {rule}")


def next_look(runs: list[AgentRun], proposals: list[AgentProposal], local_now: datetime) -> int | None:
    """Which look this item is due for, or None while it rests.

    ``runs`` are earlier looks at the same item version under the same rule.
    """
    if not runs:
        return 1
    if len(runs) >= LOOKS_PER_CHANGE:
        return None
    if any(proposal.status == "pending" for proposal in proposals):
        return None
    last = max(runs, key=lambda run: run.started_at)
    settled = [proposal.decided_at for proposal in proposals if proposal.decided_at is not None]
    settled.append(last.finished_at or last.started_at)
    if local_now < max(settled) + COOLDOWN:
        return None
    return len(runs) + 1


def _rank_key(rule: str, row: Task | Commitment) -> tuple:
    if rule == "doing_stalled":
        return (0, row.updated_at.astimezone(_UTC).isoformat(), row.title.lower())
    if rule == "overdue_lingering":
        return (1, row.due_on.isoformat(), row.title.lower())
    return (2, row.due_on.isoformat(), row.title.lower())


def stale_candidates(session: Session, local_now: datetime) -> tuple[Candidate, ...]:
    today = local_now.date()
    matches: list[tuple[str, str, Task | Commitment]] = []
    for row in session.scalars(
        select(Task).where(Task.status == "doing", Task.updated_at <= local_now - timedelta(days=STALLED_DAYS))
    ):
        matches.append(("doing_stalled", "task", row))
    for row in session.scalars(
        select(Task).where(Task.status != "done", Task.due_on <= today - timedelta(days=OVERDUE_DAYS))
    ):
        matches.append(("overdue_lingering", "task", row))
    for row in session.scalars(
        select(Commitment).where(
            Commitment.status == "open",
            Commitment.due_on.between(today, today + timedelta(days=1)),
        )
    ):
        matches.append(("commitment_due_soon", "commitment", row))
    if not matches:
        return ()

    matches.sort(key=lambda match: _rank_key(match[0], match[2]))

    # One rule per item: the highest-ranked one. If that rule is resting, the item rests.
    seen: set[tuple[str, UUID]] = set()
    best: list[tuple[str, str, Task | Commitment]] = []
    for rule, ref_type, row in matches:
        if (ref_type, row.id) in seen:
            continue
        seen.add((ref_type, row.id))
        best.append((rule, ref_type, row))

    waiting = {
        (ref_type, ref_id)
        for ref_type, ref_id in session.execute(
            select(AgentProposal.ref_type, AgentProposal.ref_id).where(
                AgentProposal.status == "pending", AgentProposal.ref_id.is_not(None)
            )
        )
    }

    runs = list(
        session.scalars(
            select(AgentRun).where(
                AgentRun.trigger.in_(STALE_RULES),
                AgentRun.started_at >= local_now - HISTORY,
            )
        )
    )
    runs_by_key: dict[tuple[str, str], list[AgentRun]] = {}
    for run in runs:
        runs_by_key.setdefault((run.trigger, run.window_key.rsplit("#", 1)[0]), []).append(run)
    proposals_by_run: dict[UUID, list[AgentProposal]] = {}
    if runs:
        for proposal in session.scalars(
            select(AgentProposal).where(AgentProposal.run_id.in_([run.id for run in runs]))
        ):
            proposals_by_run.setdefault(proposal.run_id, []).append(proposal)

    candidates: list[Candidate] = []
    for rule, ref_type, row in best:
        if (ref_type, row.id) in waiting:
            continue
        reason = stale_reason(rule, local_now, row)
        if reason is None:
            continue
        base = window_base(ref_type, row.id, row.updated_at)
        earlier = runs_by_key.get((rule, base), [])
        earlier_proposals = [proposal for run in earlier for proposal in proposals_by_run.get(run.id, [])]
        look = next_look(earlier, earlier_proposals, local_now)
        if look is None:
            continue
        candidates.append(
            Candidate(
                rule=rule,
                ref_type=ref_type,
                ref_id=row.id,
                title=row.title,
                status=row.status,
                due_on=row.due_on,
                ref_updated_at=row.updated_at,
                reason=reason,
                look=look,
            )
        )
    return tuple(candidates)


def house_day_bounds(local_now: datetime, tz_name: str) -> tuple[datetime, datetime]:
    zone = ZoneInfo(tz_name)
    today = local_now.date()
    start = datetime.combine(today, time.min, tzinfo=zone)
    end = datetime.combine(today + timedelta(days=1), time.min, tzinfo=zone)
    return start, end


def runs_today(session: Session, local_now: datetime, tz_name: str) -> int:
    start, end = house_day_bounds(local_now, tz_name)
    return (
        session.scalar(
            select(func.count()).select_from(AgentRun).where(AgentRun.started_at >= start, AgentRun.started_at < end)
        )
        or 0
    )


def build_snapshot(session: Session, local_now: datetime, settings: Settings) -> Snapshot:
    tz_name = settings.house_timezone
    local_now = local_now.astimezone(ZoneInfo(tz_name))
    start, end = house_day_bounds(local_now, tz_name)
    paused = ensure_system_state(session).paused
    enabled = settings.assistant_enabled
    proactive_today = (
        session.scalar(
            select(func.count())
            .select_from(AgentProposal)
            .where(
                AgentProposal.origin == "proactive",
                AgentProposal.created_at >= start,
                AgentProposal.created_at < end,
            )
        )
        or 0
    )
    proactive_pending = (
        session.scalar(
            select(func.count())
            .select_from(AgentProposal)
            .where(AgentProposal.origin == "proactive", AgentProposal.status == "pending")
        )
        or 0
    ) > 0
    morning_claimed = (
        session.scalar(
            select(func.count())
            .select_from(AgentRun)
            .where(AgentRun.trigger == "morning_review", AgentRun.window_key == local_now.date().isoformat())
        )
        or 0
    ) > 0
    candidates = stale_candidates(session, local_now) if enabled and not paused else ()
    return Snapshot(
        enabled=enabled,
        paused=paused,
        runs_today=runs_today(session, local_now, tz_name),
        proactive_today=proactive_today,
        proactive_pending=proactive_pending,
        morning_claimed=morning_claimed,
        candidates=candidates,
    )
