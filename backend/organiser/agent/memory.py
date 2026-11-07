"""Household memory: what may be stored, and which ten lines to hand to a run.

Remember and forget are parsed here. Nothing is written until Apply.
``last_used_at`` is stamped by the context builder on lines it kept. Embeddings go
through the Mistral client when a key is set. A postcode or a coordinate is
removed before that call. If the call cannot be made, retrieval uses words.
"""

import logging
import math
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from organiser.agent.cards import clip
from organiser.agent.mistral import MistralClient, MistralUnavailable
from organiser.agent.runner import outside_home
from organiser.config import get_settings
from organiser.jsonlog import COORD_PATTERN, POSTCODE_PATTERN
from organiser.models import MEMORY_EMBEDDING_DIM, MemoryItem

logger = logging.getLogger(__name__)

MEMORY_TEXT_LIMIT = 400
VECTOR_FLOOR = 0.15
RECENCY_DAYS = 30
# A pinned line wins a close call. It does not outrank a clear match.
PIN_BOOST = 0.05

_REMEMBER = re.compile(
    r"^\s*(?:please\s+)?remember(?:\s+(?:that|this))?\s*[:,]?\s+(.+?)\s*$",
    re.IGNORECASE | re.DOTALL,
)
_FORGET = re.compile(
    r"^\s*(?:please\s+)?forget(?:\s+(?:that|about|this))?\s*[:,]?\s+(.+?)\s*$",
    re.IGNORECASE | re.DOTALL,
)
_PREFERENCE = re.compile(
    r"\b(prefer|prefers|preferred|like|likes|love|loves|hate|hates|rather|favourite|favorite)\b",
    re.IGNORECASE,
)
_ROUTINE = re.compile(
    r"\b(every|each|usually|routine|always|weekday|weekends|mondays|tuesdays|wednesdays|thursdays|fridays|saturdays|sundays)\b",
    re.IGNORECASE,
)
# Work, on top of the Hilton, guest, colleague, and employer check.
_WORK = re.compile(
    r"\b(coworkers?|co-workers?|workmates?|workplace|payroll|work\s+emails?|work\s+phones?|at\s+work)\b",
    re.IGNORECASE,
)
_TOKEN = re.compile(r"[a-z0-9']+")
_STOP = frozenset(
    "a an the to of and or my our that this it is in on for about please at be was are".split()
)

Kind = Literal["preference", "fact", "routine"]
Source = Literal["remember", "forget", "smart-add", "manual"]


@dataclass(frozen=True)
class MemoryIntent:
    action: Literal["remember", "forget"]
    text: str


def outside_memory(text: str) -> bool:
    """Hilton, a guest, a colleague, an employer, or work does not belong here.

    A personal hotel booking can. The house guard covers the same work words.
    """
    return outside_home(text) or _WORK.search(text) is not None


def parse_memory_intent(text: str) -> MemoryIntent | None:
    """A leading remember or forget. Anything else is left for the assistant."""
    remember = _REMEMBER.match(text or "")
    if remember:
        cleaned = _clean(remember.group(1))
        return MemoryIntent("remember", cleaned) if cleaned else None
    forget = _FORGET.match(text or "")
    if forget:
        cleaned = _clean(forget.group(1))
        return MemoryIntent("forget", cleaned) if cleaned else None
    return None


def classify_kind(text: str) -> Kind:
    if _PREFERENCE.search(text):
        return "preference"
    if _ROUTINE.search(text):
        return "routine"
    return "fact"


def redact_for_model(text: str) -> str:
    """Drop the house location and any postcode or coordinate before a model sees it."""
    settings = get_settings()
    cleaned = text
    for secret in (
        settings.house_postcode.get_secret_value().strip(),
        settings.house_lat.get_secret_value().strip(),
        settings.house_lon.get_secret_value().strip(),
    ):
        if secret:
            cleaned = re.sub(re.escape(secret), " ", cleaned, flags=re.IGNORECASE)
    cleaned = POSTCODE_PATTERN.sub(" ", cleaned)
    cleaned = COORD_PATTERN.sub(" ", cleaned)
    return " ".join(cleaned.split())


def embed_query(text: str) -> list[float] | None:
    """One embedding, or None when the call cannot be made.

    The text is redacted first. The client refuses a postcode or a coordinate
    that is still present. Failures stay here: retrieval uses words instead.
    """
    redacted = redact_for_model(text)
    if not redacted:
        return None
    settings = get_settings()
    key = settings.mistral_api_key.get_secret_value().strip()
    if not key:
        return None
    client = MistralClient(
        key,
        settings.mistral_base_url,
        min(settings.mistral_timeout_seconds, 10.0),
    )
    try:
        vector = client.embed(redacted, model=settings.mistral_embed_model)
    except MistralUnavailable:
        logger.info("Embeddings are not available. Keyword matching was used.")
        return None
    finally:
        client.close()
    if len(vector) != MEMORY_EMBEDDING_DIM:
        logger.info("Embedding length was not usable. Keyword matching was used.")
        return None
    return vector


def tokens(text: str) -> set[str]:
    return {tok for tok in _TOKEN.findall(text.lower()) if tok not in _STOP and len(tok) > 2}


def keyword_words(text: str) -> list[str]:
    """Significant words, in first-seen order. Empty when the query has none."""
    seen: list[str] = []
    for tok in _TOKEN.findall((text or "").lower()):
        if tok in _STOP or len(tok) <= 2 or tok in seen:
            continue
        seen.append(tok)
    return seen


def _like_term(word: str) -> str:
    escaped = word.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def search_keywords(session: Session, query: str, *, limit: int = 50) -> list[MemoryItem]:
    """Lines for a Settings search. Words, then a phrase if the query has no word.

    Does not embed. The caller does not stamp ``last_used_at``.
    """
    raw = " ".join((query or "").split())
    if not raw:
        return []
    words = keyword_words(raw)
    if not words:
        escaped = raw.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        return list(
            session.scalars(
                select(MemoryItem)
                .where(MemoryItem.text.ilike(f"%{escaped}%", escape="\\"))
                .order_by(MemoryItem.pinned.desc(), MemoryItem.created_at.desc())
                .limit(limit)
            ).all()
        )
    found = list(
        session.scalars(
            select(MemoryItem)
            .where(or_(*(MemoryItem.text.ilike(_like_term(word), escape="\\") for word in words)))
            .limit(200)
        ).all()
    )
    return rank_keywords(found, raw)[:limit]


def rank_keywords(rows: list[MemoryItem], query: str) -> list[MemoryItem]:
    """Rank rows by how many query words they contain.

    A pin breaks a tie. This does not embed and does not drop a row for being unpinned.
    """
    words = keyword_words(query)
    if not words:
        return list(rows)

    def hits(row: MemoryItem) -> int:
        lowered = row.text.casefold()
        return sum(1 for word in words if word in lowered)

    matched = [row for row in rows if hits(row) > 0]
    matched.sort(key=lambda row: (hits(row), row.pinned, _stamp(row)), reverse=True)
    return matched


def keyword_similarity(query: str, text: str) -> float:
    wanted = tokens(query)
    if not wanted:
        return 0.0
    found = tokens(text)
    if not found:
        return 0.0
    return len(wanted & found) / len(wanted)


def remembered_title(text: str) -> str:
    return clip(f"Remembered: {text}", 200)


def forgotten_title(texts: list[str]) -> tuple[str, str]:
    """The audit line for a confirmed forget. An empty list removed nothing."""
    if not texts:
        return "Forgot: nothing confirmed", "Nothing was confirmed. Nothing was removed."
    return (
        clip("Forgot: " + "; ".join(texts), 200),
        "Confirmed. Removed from memory. Nothing left the house.",
    )


def matching_to_forget(session: Session, query: str, *, limit: int = 10) -> list[MemoryItem]:
    """Lines that share words with the forget phrase. Recency only breaks ties.

    A line with no shared word is not a match, so Apply cannot delete it.
    """
    if outside_memory(query):
        return []
    ranked: list[tuple[float, datetime, MemoryItem]] = []
    for row in _rows(session):
        if outside_memory(row.text):
            continue
        score = keyword_similarity(query, row.text)
        if score <= 0:
            continue
        ranked.append((score, _stamp(row), row))
    ranked.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return [row for _, _, row in ranked[:limit]]


def retrieve_memories(session: Session, query: str, now: datetime, *, limit: int = 10) -> list[MemoryItem]:
    """Up to ``limit`` lines for one context. The caller stamps ``last_used_at``.

    Similarity comes from pgvector when a query embedding and stored embeddings
    exist. Otherwise the same blend uses word overlap. Lines that would be sent
    with a location still in them are left out.
    """
    query = " ".join((query or "").split())
    if not query or outside_memory(query):
        return []
    rows = [row for row in _rows(session) if not outside_memory(row.text)]
    if not rows:
        return []
    distances = _distances(session, rows, query)
    scored: list[tuple[float, bool, datetime, MemoryItem]] = []
    for row in rows:
        if redact_for_model(row.text) == "":
            continue
        keyword = keyword_similarity(query, row.text)
        if row.id in distances:
            similarity = max(0.0, 1.0 - distances[row.id])
            if similarity < VECTOR_FLOOR and keyword <= 0:
                continue
            similarity = max(similarity, keyword)
        else:
            similarity = keyword
            if similarity <= 0:
                continue
        scored.append((_blend(similarity, row, now), row.pinned, _stamp(row), row))
    scored.sort(key=lambda item: (item[0], item[1], item[2]), reverse=True)
    return [row for _, _, _, row in scored[:limit]]


def _rows(session: Session) -> list[MemoryItem]:
    return list(session.scalars(select(MemoryItem).order_by(MemoryItem.created_at.desc())).all())


def _distances(session: Session, rows: list[MemoryItem], query: str) -> dict[UUID, float]:
    if not any(row.embedding is not None for row in rows):
        return {}
    vector = embed_query(query)
    if vector is None:
        return {}
    distance = MemoryItem.embedding.cosine_distance(vector)
    found = session.execute(
        select(MemoryItem.id, distance.label("distance")).where(MemoryItem.embedding.is_not(None))
    ).all()
    return {row.id: float(row.distance) for row in found}


def _blend(similarity: float, row: MemoryItem, now: datetime) -> float:
    age = max(_age_seconds(row, now), 0.0)
    recency = math.exp(-age / (RECENCY_DAYS * 86400))
    pin = PIN_BOOST if row.pinned else 0.0
    return (0.7 * similarity) + (0.3 * recency) + pin


def _age_seconds(row: MemoryItem, now: datetime) -> float:
    stamp = _stamp(row)
    moment = now if now.tzinfo is not None else now.replace(tzinfo=timezone.utc)
    return (moment - stamp).total_seconds()


def _stamp(row: MemoryItem) -> datetime:
    value = row.last_used_at or row.created_at
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _clean(captured: str) -> str:
    text = " ".join(captured.split())
    if text.endswith("."):
        text = text[:-1].rstrip()
    return text
