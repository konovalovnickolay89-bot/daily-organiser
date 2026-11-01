"""Demo household data for a local arrival screen.

Home only. Nothing here is a work task, a booking, or an order.
"""

from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from organiser.config import get_settings
from organiser.models import ActionRequest, Commitment, Event, Task
from organiser.services.system import ensure_system_state
from organiser.timeutil import house_today, utcnow


def seed_if_empty(session: Session) -> bool:
    """Insert the demo log when no tasks exist. Returns True if it inserted rows."""
    ensure_system_state(session)
    existing = session.scalar(select(func.count()).select_from(Task))
    if existing:
        return False

    today = house_today(get_settings().house_timezone)
    saturday = today + timedelta(days=(5 - today.weekday()) % 7 or 7)
    now = utcnow()

    session.add_all(
        [
            Task(
                title="Put the bins out",
                detail="Green bin this week.",
                due_on=today,
                priority="high",
                status="todo",
                owner="Nick",
            ),
            Task(
                title="Water the houseplants",
                detail="The ones on the landing dry out first.",
                due_on=today,
                priority="low",
                status="todo",
                owner="Nick",
            ),
            Task(
                title="Replace the hallway bulb",
                detail="Bulbs are in the cupboard under the stairs.",
                due_on=today - timedelta(days=1),
                priority="medium",
                status="doing",
                owner="Nick",
            ),
            Task(
                title="Book the boiler service",
                detail="Annual service. Nothing is booked yet.",
                due_on=today + timedelta(days=5),
                priority="medium",
                status="todo",
                owner="Nick",
            ),
            Commitment(
                title="Collect the dry cleaning",
                detail="Saturday, on the way back from the shops.",
                due_on=saturday,
                status="open",
                owner="Nick",
                source="manual",
            ),
            Commitment(
                title="Return the spare key to next door",
                detail="They lent it while the lock was sticking.",
                due_on=None,
                status="open",
                owner="Nick",
                source="manual",
            ),
            Commitment(
                title="Take the library books back",
                detail="Already returned.",
                due_on=today - timedelta(days=2),
                status="kept",
                owner="Nick",
                source="manual",
            ),
            Event(
                kind="system",
                title="House log started",
                body="Ops core is keeping the household log. Nothing outside the house is connected.",
                owner="Nick",
                recorded_at=now,
            ),
            Event(
                kind="note",
                title="Milk is low",
                body="Noted for the shopping list. Nothing has been ordered.",
                owner="Nick",
                recorded_at=now,
            ),
            ActionRequest(
                title="Milk is low",
                detail="Noted from the kitchen. Approving only records that you saw it.",
                mode="observe",
                status="pending",
                owner="Nick",
            ),
            ActionRequest(
                title="Boiler service is due this month",
                detail="A short reminder can be drafted. Nothing will be booked.",
                mode="advise",
                status="pending",
                owner="Nick",
            ),
            ActionRequest(
                title="Evening shop list",
                detail="Prepare a short list for tonight. Nothing will be bought.",
                mode="prepare",
                status="pending",
                owner="Nick",
            ),
            ActionRequest(
                title="Message the plumber",
                detail="Execute is not wired. Approving this only records the decision. No message will be sent.",
                mode="execute",
                status="pending",
                owner="Nick",
            ),
        ]
    )
    return True
