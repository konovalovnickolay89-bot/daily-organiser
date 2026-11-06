"""Prometheus text for this process. Counts and timings. No house text."""

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from organiser import clock
from organiser.db import get_db
from organiser.metrics import CONTENT_TYPE, METRICS
from organiser.models import AgentProposal

router = APIRouter(tags=["metrics"])


@router.get("/metrics")
def metrics(session: Session = Depends(get_db)) -> Response:
    """Request counts, Mistral calls, poll age, and the proposal queue.

    The body is Prometheus text. It does not include a title, a transcript, or a secret.
    """
    now = clock.current_time()
    try:
        pending = session.scalar(
            select(func.count()).select_from(AgentProposal).where(AgentProposal.status == "pending")
        )
        METRICS.set_proposal_queue(int(pending or 0))
    except SQLAlchemyError:
        session.rollback()
        METRICS.record_db_error(now)
        METRICS.set_proposal_queue(-1)
    return Response(content=METRICS.render(now), media_type=CONTENT_TYPE)
