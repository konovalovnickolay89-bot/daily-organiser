"""House scope for inbound text. Hilton, a guest, a colleague, an employer, or work stays out."""

from fastapi import HTTPException
from pydantic import BaseModel

from organiser.agent.runner import outside_home


def require_house(*parts: str | None) -> None:
    text = " ".join(part for part in parts if part)
    if text and outside_home(text):
        raise HTTPException(status_code=422, detail="Not for the house log.")


def require_house_fields(payload: BaseModel, *names: str) -> None:
    """Check the text fields that were sent. Unset fields are left alone."""
    data = payload.model_dump(exclude_unset=True)
    require_house(*(data[name] for name in names if isinstance(data.get(name), str)))
