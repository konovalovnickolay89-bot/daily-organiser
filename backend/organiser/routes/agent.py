"""The Mistral assistant's routes.

GET /agent only reads and never calls Mistral. GET /agent/activity is the same
kind of read: recent lines from the house log. POST /agent/proposals stores
one pending card and does not call Mistral. The other POST routes are explicit:
the box on the screen, a review the rules say is due, and Nick's two taps.
"""

import json
import logging
from collections.abc import Iterator
from datetime import datetime
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from organiser import clock
from organiser.agent.functions import RunContext
from organiser.agent.ingest import IngestRefused, ingest_proposal
from organiser.agent.mistral import MistralClient, MistralUnavailable
from organiser.agent.runner import outside_home
from organiser.agent.rules import (
    FEED_LABEL,
    FEED_PROPOSALS,
    Due,
    build_snapshot,
    house_day_bounds,
    proactive_due,
    runs_today,
)
from organiser.agent.runner import RunFailed, RunResult, feed_packet, iter_run, morning_packet, stale_packet
from organiser.agent.service import (
    HousePaused,
    ProposalClosed,
    ProposalNotFound,
    ProposalRefused,
    ProposalStale,
    apply_proposal,
    dismiss_proposal,
)
from organiser.config import get_settings
from organiser.db import get_db, get_sessionmaker
from organiser.models import AgentProposal, AgentRun
from organiser.schemas import (
    ActivityList,
    AgentResult,
    AgentState,
    AppliedChange,
    ApplyResult,
    DueRead,
    FeedRequest,
    LastReply,
    ProposalIngest,
    ProposalRead,
    ReviewRequest,
)
from organiser.services.activity import list_activity, record_line
from organiser.services.brief import morning_brief
from organiser.services.system import ensure_system_state

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agent", tags=["assistant"])

PAUSED = "The house is paused. Nothing was sent to the assistant."
OFF = "The assistant is off. Nothing was sent."
SPENT = "The assistant has used its runs for today. Nothing was sent."
FAILED = "The assistant did not finish. Nothing was changed."
VISIBLE_PROPOSALS = 10


class AssistantRunError(Exception):
    """A run ended without a reply. The detail is safe to show on the screen."""

    def __init__(self, detail: str) -> None:
        self.detail = detail


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
    row = ensure_system_state(session)
    paused = row.paused
    enabled = settings.assistant_enabled and row.assistant_enabled
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
        enabled=enabled,
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


@router.get("/activity", response_model=ActivityList)
def activity(
    session: Session = Depends(get_db),
    limit: int = Query(default=40, ge=1, le=100),
    since: datetime | None = None,
) -> ActivityList:
    """Recent house-log lines for a curator. Read only. Never calls Mistral."""
    return ActivityList(items=list_activity(session, limit=limit, since=since))


@router.post("/proposals", response_model=ProposalRead, status_code=201)
def propose(payload: ProposalIngest, session: Session = Depends(get_db)) -> ProposalRead:
    """Store one pending task card. Does not create a task, and does not call Mistral."""
    try:
        proposal = ingest_proposal(
            session,
            title=payload.title,
            due_on=payload.due_on,
            reason=payload.reason,
            source=payload.source,
            now=_local_now(),
        )
    except IngestRefused as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from None
    session.commit()
    return _proposal(proposal)


def _failure_detail(exc: Exception) -> str:
    if isinstance(exc, MistralUnavailable):
        return "The assistant could not be reached. Nothing was changed."
    if isinstance(exc, RunFailed):
        text = str(exc)
        if text == "The assistant did not finish.":
            return FAILED
        if text == "The assistant took too long.":
            return "The assistant took too long. Nothing was changed."
        return f"{text} Nothing was changed."
    return FAILED


def _fail_run(session: Session, run_id: UUID, exc: Exception) -> None:
    session.rollback()
    failed = session.get(AgentRun, run_id)
    if failed is not None:
        failed.status = "failed"
        failed.error = str(exc)[:200] or type(exc).__name__
        failed.finished_at = clock.current_time()
        session.commit()
    if not isinstance(exc, (MistralUnavailable, RunFailed)):
        logger.exception("Assistant run %s failed.", run_id)


def _complete(session: Session, run: AgentRun, ctx: RunContext, result: RunResult) -> AgentResult:
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


def _execute(
    session: Session,
    client: MistralClient,
    run: AgentRun,
    ctx: RunContext,
    packet: str,
) -> AgentResult:
    """Run to the end. A failure is 424, which the page can read. 502 is a proxy error page."""
    run_id = run.id
    try:
        outcome: RunResult | None = None
        for item in iter_run(client, get_settings().mistral_agent_id.strip(), ctx, packet):
            if isinstance(item, RunResult):
                outcome = item
        if outcome is None:
            raise RunFailed("The assistant did not finish.")
    except Exception as exc:
        _fail_run(session, run_id, exc)
        raise AssistantRunError(_failure_detail(exc)) from None
    return _complete(session, run, ctx, outcome)


def _http_run_error(exc: AssistantRunError) -> HTTPException:
    return HTTPException(status_code=424, detail=exc.detail)


def _guard_feed(session: Session) -> None:
    settings = get_settings()
    local_now = _local_now()
    row = ensure_system_state(session)
    if row.paused:
        raise HTTPException(status_code=409, detail=PAUSED)
    if not settings.assistant_enabled or not row.assistant_enabled:
        raise HTTPException(status_code=503, detail=OFF)
    if runs_today(session, local_now, settings.house_timezone) >= settings.agent_runs_per_day:
        raise HTTPException(status_code=429, detail=SPENT)


def _wants_stream(request: Request) -> bool:
    return "text/event-stream" in request.headers.get("accept", "")


def _start_feed(session: Session, text: str, local_now) -> AgentRun:
    """Accept one line from the box. The line is in the log even if the run fails."""
    run = AgentRun(
        trigger="feed",
        window_key=f"feed:{uuid4()}",
        input_text=text,
        status="running",
        started_at=local_now,
    )
    session.add(run)
    if not outside_home(text):
        record_line(
            session,
            kind="note",
            title=f"Added: {text}",
            body="Written in the box. Nothing was created until a card is applied.",
        )
    session.commit()
    return run


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def _acquire_client(app) -> tuple[MistralClient | None, object]:
    """The test double when one is installed, otherwise a client this call closes."""
    override = app.dependency_overrides.get(get_mistral)
    if override is not None:
        return override(), None
    settings = get_settings()
    if not settings.assistant_enabled:
        return None, None
    client = MistralClient(
        settings.mistral_api_key.get_secret_value(),
        settings.mistral_base_url,
        settings.mistral_timeout_seconds,
    )
    return client, client.close


def _feed_events(app, text: str) -> Iterator[str]:
    """Steps, then the cards or one error. The status stays 200 so a proxy will not replace the body."""
    yield _sse("step", {"step": "received"})
    session = get_sessionmaker()()
    close = None
    try:
        client, close = _acquire_client(app)
        if client is None:
            yield _sse("error", {"detail": OFF})
            return
        settings = get_settings()
        local_now = _local_now()
        if ensure_system_state(session).paused:
            yield _sse("error", {"detail": PAUSED})
            return
        run = _start_feed(session, text, local_now)
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
        packet = feed_packet(local_now, settings.house_timezone, FEED_PROPOSALS, text)
        try:
            outcome: RunResult | None = None
            for item in iter_run(client, settings.mistral_agent_id.strip(), ctx, packet):
                if isinstance(item, str):
                    yield _sse("step", {"step": item})
                elif isinstance(item, RunResult):
                    outcome = item
            if outcome is None:
                raise RunFailed("The assistant did not finish.")
        except Exception as exc:
            _fail_run(session, run.id, exc)
            yield _sse("error", {"detail": _failure_detail(exc)})
            return
        yield _sse("done", _complete(session, run, ctx, outcome).model_dump(mode="json"))
    finally:
        if close is not None:
            close()
        session.close()


@router.post("/feed", response_model=AgentResult)
def feed(
    payload: FeedRequest,
    request: Request,
    session: Session = Depends(get_db),
    client: MistralClient | None = Depends(get_mistral),
) -> AgentResult | StreamingResponse:
    """Hand the assistant one entry from the box. It may propose; it changes nothing.

    ``Accept: text/event-stream`` sends the steps as they happen, then the cards
    or one error event. Anything else gets the same result as JSON.
    """
    _guard_feed(session)
    if client is None:
        raise HTTPException(status_code=503, detail=OFF)
    if _wants_stream(request):
        return StreamingResponse(
            _feed_events(request.app, payload.text),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    settings = get_settings()
    local_now = _local_now()
    run = _start_feed(session, payload.text, local_now)
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
    try:
        return _execute(session, client, run, ctx, packet)
    except AssistantRunError as exc:
        raise _http_run_error(exc) from None


@router.post("/review", response_model=AgentResult)
def review(
    payload: ReviewRequest,
    session: Session = Depends(get_db),
    client: MistralClient | None = Depends(get_mistral),
) -> AgentResult:
    """Run the one review GET /agent said is due. Each window runs once."""
    settings = get_settings()
    local_now = _local_now()
    row = ensure_system_state(session)
    paused = row.paused
    session.commit()
    if paused:
        raise HTTPException(status_code=409, detail=PAUSED)
    if client is None or not row.assistant_enabled:
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
    try:
        return _execute(session, client, run, ctx, packet)
    except AssistantRunError as exc:
        raise _http_run_error(exc) from None


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
    except ProposalRefused as exc:
        session.commit()
        raise HTTPException(status_code=422, detail=exc.detail) from None
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
