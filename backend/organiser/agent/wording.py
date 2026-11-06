"""One short note per catch-up card.

Mistral writes the sentence. The template is used when it is off, down, or
unusable, and that card is marked so the screen can say so. The call is one
completion for the whole pass, not an agent run, and it does not count toward
the daily run cap.
"""

import logging
import re

from organiser.agent.mistral import MistralUnavailable
from organiser.agent.reach import mark_down, mark_up
from organiser.agent.runner import outside_home
from organiser.config import Settings

logger = logging.getLogger(__name__)

NOTE_LIMIT = 160
_LEADING = re.compile(r"^\d+[\).\]]\s*")


def _accept(text: str) -> str | None:
    line = " ".join(text.split())
    line = _LEADING.sub("", line).strip(" \"'")
    if not line or line.casefold() in {"fallback", "fallback."}:
        return None
    if len(line) < 2 or len(line) > NOTE_LIMIT:
        return None
    if outside_home(line):
        return None
    folded = line.casefold()
    if "http://" in folded or "https://" in folded:
        return None
    return line


def _templates(drafts) -> list[tuple[str, bool]]:
    return [(draft.note, True) for draft in drafts]


def write_notes(client, settings: Settings, drafts) -> list[tuple[str, bool]]:
    """Return ``(note, fallback_used)`` for each draft, in order."""
    rows = tuple(drafts)
    if not rows:
        return []
    if client is None:
        return _templates(rows)
    lines = [f"{index}. {draft.title} — {draft.reason}" for index, draft in enumerate(rows, start=1)]
    prompt = (
        "Write one short note for each numbered household item. "
        "Reply with exactly one line per item, in the same order, under 16 words. "
        "No numbers, no greeting, no sign-off. Use only the fact on that line. "
        "Do not add a person, a place, or a time you were not given.\n" + "\n".join(lines)
    )
    try:
        text = client.complete(
            model=settings.mistral_model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=40 * len(rows),
        )
    except MistralUnavailable:
        logger.info("catch-up wording failed (MistralUnavailable)")
        mark_down()
        return _templates(rows)
    parts = [part.strip() for part in str(text).splitlines() if part.strip()]
    if len(parts) != len(rows):
        return _templates(rows)
    notes: list[tuple[str, bool]] = []
    for draft, part in zip(rows, parts):
        cleaned = _accept(part)
        if cleaned is None:
            notes.append((draft.note, True))
        else:
            notes.append((cleaned, False))
    if any(not used for _, used in notes):
        mark_up()
    return notes
