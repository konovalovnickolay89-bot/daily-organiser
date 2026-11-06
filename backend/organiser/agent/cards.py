"""Card text, written by code from the change itself.

The model's words go in the reason line. The summary line is built here, so the
card always says exactly what Apply will do.
"""

from datetime import date

from organiser.domain import COMMITMENT_STATUS_LABELS, PRIORITY_LABELS, TASK_STATUS_LABELS

SUMMARY_LIMIT = 240
DETAIL_LIMIT = 4000


def clip(text: str, limit: int = SUMMARY_LIMIT) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def short_date(value: date) -> str:
    """Fri 6 Nov."""
    return f"{value.strftime('%a')} {value.day} {value.strftime('%b')}"


def note_line(day: date, note: str) -> str:
    """One dated line appended to an item's detail: "2 Nov: Filters are 22 mm"."""
    return f"{day.day} {day.strftime('%b')}: {note}"


def with_note(detail: str | None, line: str) -> str:
    if detail and detail.strip():
        return f"{detail.rstrip()}\n{line}"
    return line


def _due(changes: dict) -> str | None:
    value = changes.get("due_on")
    return f"due {short_date(date.fromisoformat(value))}" if value else None


def summarise(action: str, changes: dict, row: object | None) -> str:
    if action == "create_task":
        parts = [f"New task: {changes['title']}", _due(changes)]
        priority = changes.get("priority")
        if priority and priority != "medium":
            parts.append(f"{PRIORITY_LABELS[priority]} priority")
        return clip(" · ".join(part for part in parts if part))
    if action == "create_commitment":
        parts = [f"New commitment: {changes['title']}", _due(changes)]
        return clip(" · ".join(part for part in parts if part))
    if action == "create_shopping_item":
        return clip(f"Add to shopping: {changes['name']}")
    if row is None:
        raise ValueError(f"{action} needs the row it changes")
    title = getattr(row, "title")
    if action == "add_note":
        return clip(f"Note on {title}: “{changes['note']}”")

    labels = TASK_STATUS_LABELS if action == "update_task" else COMMITMENT_STATUS_LABELS
    parts: list[str] = []
    if "status" in changes:
        parts.append(f"{labels.get(getattr(row, 'status'), getattr(row, 'status'))} → {labels[changes['status']]}")
    if "due_on" in changes:
        old = getattr(row, "due_on")
        parts.append(f"due {short_date(old) if old else 'no date'} → {short_date(date.fromisoformat(changes['due_on']))}")
    if "priority" in changes:
        old_priority = getattr(row, "priority")
        parts.append(f"{PRIORITY_LABELS.get(old_priority, old_priority)} → {PRIORITY_LABELS[changes['priority']]} priority")
    if "title" in changes:
        parts.append(f"rename to “{changes['title']}”")
    if "detail" in changes:
        parts.append("new detail")
    return clip(f"{title}: {'; '.join(parts)}")
