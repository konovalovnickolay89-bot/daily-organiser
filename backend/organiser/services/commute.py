"""A commute shift is start, end, and a place. Origin is home.

The label ``Wembley`` means Wembley Park. Anything else is refused.
Nothing here calls TfL or Bantō, and a refusal writes no row.
"""

from datetime import datetime

from sqlalchemy.orm import Session

from organiser.agent.runner import outside_home
from organiser.config import COMMUTE_ORIGIN, commute_point_for_label
from organiser.domain import DEFAULT_OWNER
from organiser.services.events import record_event


class ShiftRefused(Exception):
    def __init__(self, detail: str) -> None:
        self.detail = detail
        super().__init__(detail)


_FIELDS = ("start", "end", "location_label")


def _time(value: object, name: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ShiftRefused(f"Give the shift a {name}.")
    text = value.strip()
    if outside_home(text):
        raise ShiftRefused("Not for the house log.")
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        raise ShiftRefused(f"{name} is not a time.") from None
    if parsed.tzinfo is None or parsed.tzinfo.utcoffset(parsed) is None:
        raise ShiftRefused(f"{name} needs a timezone.")
    return parsed


def normalise_shift(data: object) -> dict:
    """The only accepted body: start, end, and location_label. No extra field is kept."""
    if not isinstance(data, dict):
        raise ShiftRefused("The shift body must be an object.")
    if set(data) != set(_FIELDS):
        raise ShiftRefused("The shift body is only start, end, and location_label.")
    start = _time(data["start"], "start")
    end = _time(data["end"], "end")
    if end <= start:
        raise ShiftRefused("The shift end is not after the start.")
    label = data["location_label"]
    if not isinstance(label, str) or not label.strip():
        raise ShiftRefused("Give the shift a place.")
    if outside_home(label):
        raise ShiftRefused("Not for the house log.")
    point = commute_point_for_label(label)
    if point is None:
        raise ShiftRefused("That place is not a house commute.")
    return {
        "start": start.isoformat(),
        "end": end.isoformat(),
        "location_label": point,
        "origin": COMMUTE_ORIGIN,
    }


def record_shift(session: Session, shift: dict) -> dict:
    """Write one house line from a shift that has already been accepted."""
    record_event(
        session,
        kind="system",
        title="Commute shift",
        body=(
            f"{shift['start']} to {shift['end']}. {shift['location_label']}, from home. "
            "Nothing was booked."
        ),
        owner=DEFAULT_OWNER,
    )
    return shift
