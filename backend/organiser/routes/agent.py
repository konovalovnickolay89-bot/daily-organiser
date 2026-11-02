"""The Mistral assistant's routes.

GET /agent only reads and never calls Mistral. The POST routes are explicit:
the box on the screen, a review the rules say is due, and Nick's two taps.
"""

import logging
from collections.abc import Iterator
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from organiser import clock
from organiser.agent.functions import RunContext
from organiser.agent.mistral import MistralClient, MistralUnavailable
from organiser.agent.rules import (
    FEED_LABEL,
    FEED_PROPOSALS,
    Due,
    build_snapshot,
    house_day_bounds,
    proactive_due,
    runs_today,
)
from organiser.agent.runner import RunFailed, feed_packet, morning_packet, run_agent, stale_packet
from organiser.agent.service import (
    HousePaused,
    ProposalClosed,
    ProposalNotFound,
    ProposalStale,
    apply_proposal,
    dismiss_proposal,
)
from organiser.config import get_settings
from organiser.db import get_db
from organiser.models import AgentProposal, AgentRun
from organiser.schemas import (
    AgentResult,
    AgentState,
    AppliedChange,
    ApplyResult,
    DueRead,
    FeedRequest,
    LastReply,
    ProposalRead,
    ReviewRequest,
)
from organiser.services.brief import morning_brief
from organiser.services.system import ensure_system_state

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agent", tags=["assistant"])

PAUSED = "The house is paused. Nothing was sent to the assistant."
OFF = "The assistant is off. Nothing was sent."
SPENT = "The assistant has used its runs for today. Nothing was sent."
VISIBLE_PROPOSALS = 10


def get_mistral() -> Iterator[MistralClient | None]:
    """The Mistral client, or None while the key or the agent id is missing."""
    settings = get_settings()
    if not settings.assistant_enabled:
        yield None
        return
    client = MistralClient(
        settings.mistral_api_key.get_secret_value(),
        settings.mistral_base_url,
        settings.mistral_timeout_seconds,
    )
    try:
        yield client
    finally:
        client.close()


def _local_now():
    return clock.current_time().astimezone(ZoneInfo(get_settings().house_timezone))


def _proposal(row: AgentProposal) -> ProposalRead:
    return ProposalRead.model_validate(row)


def _due(session: Session, local_now) -> tuple[Due | None, object]:
    settings = get_settings()
    snapshot = build_snapshot(session, local_now, settings)
    due = proactive_due(
        local_now,
        snapshot,
        runs_per_day=settings.agent_runs_per_day,
        proactive_per_day=settings.agent_proactive_per_day,
    )
    return due, snapshot


@router.get("", response_model=AgentState)
def get_agent(session: Session = Depends(get_db)) -> AgentState:
    settings = get_settings()
    local_now = _local_now()
    paused = ensure_system_state(session).paused
    session.commit()
    due, snapshot = _due(session, local_now)

    proposals: list[ProposalRead] = []
    if not paused:
        proposals = [
            _proposal(row)
            for row in session.scalars(
                select(AgentProposal)
                .where(AgentProposal.status == "pending")
                .order_by(AgentProposal.created_at.desc())
                .limit(VISIBLE_PROPOSALS)
            )
        ]

    start, end = house_day_bounds(local_now, settings.house_timezone)
    last = session.scalars(
        select(AgentRun)
        .where(
            AgentRun.status == "done",
            AgentRun.reply.is_not(None),
            AgentRun.started_at >= start,
            AgentRun.started_at < end,
        )
        .order_by(AgentRun.started_at.desc())
        .limit(1)
    ).first()

    return AgentState(
        enabled=settings.assistant_enabled,
        paused=paused,
        as_of=local_now,
        house_date=local_now.date(),
        due=DueRead(trigger=due.trigger, window_key=due.window_key, label=due.label) if due else None,
        runs_left_today=max(0, settings.agent_runs_per_day - snapshot.runs_today),
        proactive_left_today=max(0, settings.agent_proactive_per_day - snapshot.proactive_today),
        last_reply=LastReply(text=last.reply, at=last.finished_at or last.started_at, trigger=last.trigger)
        if last
        else None,
        proposals=proposals,
    )


def _execute(
    session: Session,
    client: MistralClient,
    run: AgentRun,
    ctx: RunContext,
    packet: str,
) -> AgentResult:
    run_id = run.id
    try:
        result = run_agent(client, get_settings().mistral_agent_id.strip(), ctx, packet)
    except Exception as exc:
        session.rollback()
        failed = session.get(AgentRun, run_id)
        if failed is not None:
            failed.status = "failed"
            failed.error = str(exc)[:200] or type(exc).__name__
            failed.finished_at = clock.current_time()
            session.commit()
        if isinstance(exc, MistralUnavailable):
            detail = "The assistant could not be reached. Nothing was changed."
        elif isinstance(exc, RunFailed):
            detail = f"{exc} Nothing was changed."
        else:
            logger.exception("Assistant run %s failed.", run_id)
            detail = "The assistant run failed. Nothing was changed."
        raise HTTPException(status_code=502, detail=detail) from None

    run.status = "done"
    run.reply = result.reply
    run.searched = result.searched
    run.finished_at = clock.current_time()
    session.commit()
    return AgentResult(
        run_id=run.id,
        trigger=run.trigger,
        reply=result.reply,
        searched=result.searched,
        proposals=[_proposal(row) for row in ctx.proposals],
    )


@router.post("/feed", response_model=AgentResult)
def feed(
    payload: FeedRequest,
    session: Session = Depends(get_db),
    client: MistralClient | None = Depends(get_mistral),
) -> AgentResult:
    """Hand the assistant one entry from the box. It may propose; it changes nothing."""
    settings = get_settings()
    local_now = _local_now()
    if ensure_system_state(session).paused:
        raise HTTPException(status_code=409, detail=PAUSED)
    if client is None:
        raise HTTPException(status_code=503, detail=OFF)
    if runs_today(session, local_now, settings.house_timezone) >= settings.agent_runs_per_day:
        raise HTTPException(status_code=429, detail=SPENT)

    run = AgentRun(
        trigger="feed",
        window_key=f"feed:{uuid4()}",
        input_text=payload.text,
        status="running",
        started_at=local_now,
    )
    session.add(run)
    session.commit()
    ctx = RunContext(
        session=session,
        now=local_now,
        tz_name=settings.house_timezone,
        run=run,
        origin="feed",
        rule="feed",
        label=FEED_LABEL,
        max_proposals=FEED_PROPOSALS,
    )
    packet = feed_packet(local_now, settings.house_timezone, FEED_PROPOSALS, payload.text)
    return _execute(session, client, run, ctx, packet)


@router.post("/review", response_model=AgentResult)
def review(
    payload: ReviewRequest,
    session: Session = Depends(get_db),
    client: MistralClient | None = Depends(get_mistral),
) -> AgentResult:
    """Run the one review GET /agent said is due. Each window runs once."""
    settings = get_settings()
    local_now = _local_now()
    paused = ensure_system_state(session).paused
    session.commit()
    if paused:
        raise HTTPException(status_code=409, detail=PAUSED)
    if client is None:
        raise HTTPException(status_code=503, detail=OFF)
    due, _ = _due(session, local_now)
    if due is None or due.trigger != payload.trigger.value or due.window_key != payload.window_key:
        raise HTTPException(status_code=409, detail="Nothing is due.")

    run = AgentRun(trigger=due.trigger, window_key=due.window_key, status="running", started_at=local_now)
    session.add(run)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=409, detail="This review has already run.") from None

    ctx = RunContext(
        session=session,
        now=local_now,
        tz_name=settings.house_timezone,
        run=run,
        origin="proactive",
        rule=due.trigger,
        label=due.label,
        max_proposals=due.max_proposals,
    )
    if due.candidate is None:
        brief = morning_brief(session, local_now.date(), paused)
        packet = morning_packet(local_now, settings.house_timezone, due.max_proposals, brief)
    else:
        packet = stale_packet(local_now, settings.house_timezone, due.max_proposals, due.candidate)
    return _execute(session, client, run, ctx, packet)


@router.post("/proposals/{proposal_id}/apply", response_model=ApplyResult)
def apply(proposal_id: UUID, session: Session = Depends(get_db)) -> ApplyResult:
    """Make exactly the proposed change to one row. Nothing leaves the house."""
    now = clock.current_time()
    try:
        proposal, applied = apply_proposal(session, proposal_id, now)
    except HousePaused:
        raise HTTPException(status_code=409, detail="The house is paused. Nothing was applied.") from None
    except ProposalNotFound:
        raise HTTPException(status_code=404, detail="No such proposal.") from None
    except ProposalClosed:
        raise HTTPException(status_code=409, detail="This has already been decided.") from None
    except ProposalStale:
        session.commit()
        raise HTTPException(
            status_code=409,
            detail="The item changed since this was proposed. Nothing was applied.",
        ) from None
    session.commit()
    return ApplyResult(proposal=_proposal(proposal), applied=AppliedChange(**applied))


@router.post("/proposals/{proposal_id}/dismiss", response_model=ProposalRead)
def dismiss(proposal_id: UUID, session: Session = Depends(get_db)) -> ProposalRead:
    """Not now. The item rests for 72 hours."""
    try:
        proposal = dismiss_proposal(session, proposal_id, clock.current_time())
    except ProposalNotFound:
        raise HTTPException(status_code=404, detail="No such proposal.") from None
    except ProposalClosed:
        raise HTTPException(status_code=409, detail="This has already been decided.") from None
    session.commit()
    return _proposal(proposal)
