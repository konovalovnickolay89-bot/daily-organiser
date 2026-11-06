"""X rows in this database. A poll and a webhook share this path. A post does not."""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from organiser.agent.runner import outside_home
from organiser.domain import DEFAULT_OWNER
from organiser.models import XConnection, XCursor, XItem, XMeter, XPostAudit, XWatch
from organiser.services.events import record_event

DRAFT_DAYS = 7
TEXT_LIMIT = 1000
DRAFT_LIMIT = 280
WATCH_LIMIT = 20
HANDLE = re.compile(r"^[A-Za-z0-9_]{1,15}$")
KEYWORD = re.compile(r"[A-Za-z0-9][A-Za-z0-9 _-]{0,79}")
_X_HOSTS = {"x.com", "www.x.com", "twitter.com", "www.twitter.com"}
LABELS = {"bookmark": "Bookmark", "watch_match": "Watch", "draft": "Draft"}


class XRejected(Exception):
    def __init__(self, detail: str, status: int = 422, *, persist: bool = False):
        self.detail = detail
        self.status = status
        self.persist = persist
        super().__init__(detail)


def expire_drafts(session: Session, now: datetime) -> int:
    rows = session.scalars(
        select(XItem).where(
            XItem.kind == "draft",
            XItem.status == "pending",
            XItem.expires_at.is_not(None),
            XItem.expires_at <= now,
        )
    ).all()
    for row in rows:
        row.status = "expired"
        row.decided_at = now
    return len(rows)


def _clip(text: str, limit: int) -> str:
    cleaned = " ".join(text.split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 1].rstrip() + "…"


def _handle(value: str | None) -> str | None:
    if value is None:
        return None
    handle = value.strip()
    if handle.startswith("@"):
        handle = handle[1:]
    if not HANDLE.fullmatch(handle):
        return None
    return handle.lower()


def _status_url(tweet_id: str, author: str | None) -> str:
    if author:
        return f"https://x.com/{author}/status/{tweet_id}"
    return f"https://x.com/i/web/status/{tweet_id}"


def _safe_url(url: object, tweet_id: str, author: str | None) -> str:
    if isinstance(url, str) and url.startswith("https://"):
        host = url.split("/", 3)[2].lower() if url.count("/") >= 2 else ""
        if host in _X_HOSTS and len(url) <= 300:
            return url
    return _status_url(tweet_id, author)


def _id_gt(left: str, right: str | None) -> bool:
    if not right:
        return True
    try:
        return int(left) > int(right)
    except ValueError:
        return left > right


def cursor_since(session: Session, name: str) -> str | None:
    row = session.get(XCursor, name)
    return row.since_id if row is not None else None


def save_cursor(session: Session, name: str, since_id: str | None, now: datetime) -> None:
    if not since_id or not since_id.isdigit():
        return
    row = session.get(XCursor, name)
    if row is None:
        session.add(XCursor(name=name, since_id=since_id, updated_at=now))
        return
    if _id_gt(since_id, row.since_id):
        row.since_id = since_id
        row.updated_at = now


def ensure_meter(session: Session, now: datetime) -> XMeter:
    row = session.get(XMeter, 1)
    if row is None:
        row = XMeter(id=1, updated_at=now)
        session.add(row)
        session.flush()
    return row


def note_limits(
    session: Session,
    now: datetime,
    *,
    credits_remaining: int | None = None,
    rate_remaining: int | None = None,
    rate_reset_at: datetime | None = None,
    error_class: str | None = None,
    backoff_until: datetime | None = None,
    polled: bool = False,
) -> XMeter:
    row = ensure_meter(session, now)
    if credits_remaining is not None:
        row.credits_remaining = credits_remaining
    if rate_remaining is not None:
        row.rate_remaining = rate_remaining
    if rate_reset_at is not None:
        row.rate_reset_at = rate_reset_at
    if backoff_until is not None:
        row.backoff_until = backoff_until
    if error_class is not None:
        row.last_error_class = error_class[:40]
    elif polled:
        row.last_error_class = None
    if polled:
        row.last_poll_at = now
        row.backoff_until = None if backoff_until is None else backoff_until
    row.updated_at = now
    return row


def meter_view(session: Session, *, enabled: bool, now: datetime) -> dict:
    row = session.get(XMeter, 1)
    connected = session.get(XConnection, 1) is not None and enabled
    backing = bool(row and row.backoff_until and row.backoff_until > now and connected)
    return {
        "enabled": enabled,
        "connected": connected,
        "credits_remaining": None if row is None or not enabled else row.credits_remaining,
        "rate_remaining": None if row is None or not enabled else row.rate_remaining,
        "backing_off": backing,
        "attention": None if row is None or not enabled else row.last_error_class,
    }


def _outside(text: str, author: str | None) -> bool:
    if outside_home(text):
        return True
    return bool(author and outside_home(author))


def remember_external(
    session: Session,
    *,
    kind: str,
    external_id: str,
    text: str,
    author: str | None,
    url: str | None,
    source: str,
    now: datetime,
    strict: bool,
    since_id: str | None = None,
) -> str | None:
    if not external_id.isdigit():
        if strict:
            raise XRejected("Give the post an id.")
        return None
    if since_id and not _id_gt(external_id, since_id):
        return None
    cleaned = _clip(text, TEXT_LIMIT)
    if not cleaned or cleaned == "…":
        if strict:
            raise XRejected("Give the item some text.")
        return None
    handle = _handle(author) if author else None
    if author and handle is None:
        if strict:
            raise XRejected("The author is a handle.")
        handle = None
    if _outside(cleaned, handle):
        if strict:
            raise XRejected("Not for the house log.")
        return None
    existing = session.scalar(select(XItem).where(XItem.kind == kind, XItem.external_id == external_id))
    if existing is not None:
        return str(existing.id)
    from organiser.services.settings import daily_cap_reached

    if daily_cap_reached(session, now):
        if strict:
            raise XRejected("The daily cap is full.", 409)
        return None
    row = XItem(
        kind=kind,
        external_id=external_id,
        author=handle,
        text=cleaned,
        url=url or _status_url(external_id, handle),
        status="pending",
        source=source,
        created_at=now,
    )
    session.add(row)
    session.flush()
    return str(row.id)


def create_draft(session: Session, text: str, reason: str, now: datetime, source: str) -> XItem:
    cleaned = " ".join(text.split())
    why = " ".join(reason.split())
    if not cleaned:
        raise XRejected("The draft is empty.")
    if len(cleaned) > DRAFT_LIMIT:
        raise XRejected("A post is at most 280 characters.")
    if not why:
        raise XRejected("Say why in under 20 words.")
    if _outside(cleaned, None) or outside_home(why):
        raise XRejected("Not for the house log.")
    waiting = session.scalar(
        select(XItem).where(XItem.kind == "draft", XItem.status == "pending", XItem.text == cleaned)
    )
    if waiting is not None:
        raise XRejected("That draft is already waiting.", 409)
    pending = session.scalar(
        select(func.count()).select_from(XItem).where(XItem.kind == "draft", XItem.status == "pending")
    )
    if int(pending or 0) >= 5:
        raise XRejected("Too many drafts are waiting.", 409)
    from organiser.services.settings import daily_cap_reached, draft_expiry_days

    if daily_cap_reached(session, now):
        raise XRejected("The daily cap is full.", 409)
    row = XItem(
        kind="draft",
        text=cleaned,
        reason=why[:300],
        status="pending",
        source=source,
        created_at=now,
        expires_at=now + timedelta(days=draft_expiry_days(session)),
    )
    session.add(row)
    session.flush()
    return row


def _pending_filter(now: datetime):
    return (XItem.status == "pending") & or_(XItem.expires_at.is_(None), XItem.expires_at > now)


def cards(session: Session, now: datetime) -> list[XItem]:
    expire_drafts(session, now)
    return list(
        session.scalars(select(XItem).where(_pending_filter(now)).order_by(XItem.created_at.desc()).limit(20)).all()
    )


def card_body(row: XItem) -> dict:
    if row.kind == "draft":
        detail = row.reason
    elif row.author:
        detail = f"@{row.author}"
    else:
        detail = None
    return {
        "id": row.id,
        "kind": row.kind,
        "summary": _clip(row.text, 240),
        "detail": detail,
        "url": row.url,
        "expires_at": row.expires_at,
    }


def brief_section(session: Session, now: datetime) -> dict | None:
    from organiser.services.settings import from_x_max

    rows = list(
        session.scalars(
            select(XItem).where(_pending_filter(now)).order_by(XItem.created_at.desc()).limit(from_x_max(session))
        ).all()
    )
    if not rows:
        return None
    count = len(rows)
    summary = "1 from X" if count == 1 else f"{count} from X"
    return {
        "key": "x",
        "title": "From X",
        "placeholder": False,
        "summary": summary,
        "items": [
            {
                "id": row.id,
                "title": _clip(row.text, 200),
                "meta": LABELS.get(row.kind, "X") + (f" · @{row.author}" if row.author else ""),
            }
            for row in rows
        ],
    }


def add_watch(session: Session, kind: str, value: str, now: datetime) -> XWatch:
    if kind not in {"account", "keyword"}:
        raise XRejected("A watch is an account or a keyword.")
    raw = " ".join(value.split())
    if kind == "account":
        stored = _handle(raw)
        if stored is None:
            raise XRejected("An account is a handle.")
    else:
        if not KEYWORD.fullmatch(raw):
            raise XRejected("A keyword is plain words.")
        stored = raw.lower()
    if outside_home(stored):
        raise XRejected("Not for the house log.")
    rows = list(session.scalars(select(XWatch).where(XWatch.kind == kind)).all())
    for existing in rows:
        if existing.value.casefold() == stored.casefold():
            return existing
    total = session.scalar(select(func.count()).select_from(XWatch))
    if int(total or 0) >= WATCH_LIMIT:
        raise XRejected("The watch list is full.", 409)
    row = XWatch(kind=kind, value=stored, created_at=now)
    session.add(row)
    session.flush()
    return row


def remove_watch(session: Session, watch_id: UUID) -> None:
    row = session.get(XWatch, watch_id)
    if row is None:
        raise XRejected("That watch is not here.", 404)
    session.delete(row)


def watches(session: Session) -> list[XWatch]:
    return list(session.scalars(select(XWatch).order_by(XWatch.created_at.asc())).all())


def search_query(kind: str, value: str) -> str:
    if kind == "account":
        return f"from:{value} -is:retweet"
    if " " in value:
        return f'"{value}" -is:retweet'
    return f"{value} -is:retweet"


def _load(session: Session, item_id: UUID) -> XItem:
    row = session.get(XItem, item_id, with_for_update=True)
    if row is None:
        raise XRejected("That card is not here.", 404)
    return row


def apply_item(session: Session, item_id: UUID, now: datetime) -> XItem:
    row = _load(session, item_id)
    if row.status != "pending":
        raise XRejected("That card is already settled.", 409)
    if row.kind == "draft":
        raise XRejected("A draft is posted from its card.", 422)
    row.status = "applied"
    row.decided_at = now
    record_event(
        session,
        kind="note",
        title=_clip(row.text, 180),
        body="Kept from X. Nothing was sent.",
        owner=DEFAULT_OWNER,
    )
    return row


def dismiss_item(session: Session, item_id: UUID, now: datetime) -> XItem:
    row = _load(session, item_id)
    if row.status != "pending":
        raise XRejected("That card is already settled.", 409)
    row.status = "dismissed"
    row.decided_at = now
    return row


def ingest_webhook(session: Session, body: dict, now: datetime) -> dict:
    allowed = {"event", "id", "text", "author", "url"}
    if set(body) - allowed or "text" not in body:
        raise XRejected("The X body is text, and optionally id, author, and url.")
    event = body.get("event")
    kind = {"x.bookmark": "bookmark", "x.watch_match": "watch_match", "x.draft": "draft"}.get(
        event if isinstance(event, str) else ""
    )
    if kind is None:
        raise XRejected("Unknown event.", 404)
    text = body.get("text")
    if not isinstance(text, str) or not text.strip():
        raise XRejected("Give the item some text.")
    author = body.get("author")
    if author is not None and not isinstance(author, str):
        raise XRejected("The author is a handle.")
    if kind == "draft":
        if body.get("id") or body.get("url") or author:
            raise XRejected("A draft is text only.")
        row = create_draft(session, text, "From the relay.", now, "webhook")
        return {"id": str(row.id), "kind": "draft"}
    external = body.get("id")
    if not isinstance(external, str) or not external.isdigit():
        raise XRejected("Give the post an id.")
    handle = _handle(author) if isinstance(author, str) else None
    if isinstance(author, str) and author.strip() and handle is None:
        raise XRejected("The author is a handle.")
    url = _safe_url(body.get("url"), external, handle)
    item_id = remember_external(
        session,
        kind=kind,
        external_id=external,
        text=text,
        author=handle,
        url=url,
        source="webhook",
        now=now,
        strict=True,
    )
    return {"id": item_id, "kind": kind}


def apply_http_error(session: Session, status: int, now: datetime, *, credits: int | None, rate: int | None, reset_at: datetime | None) -> str:
    """Record a backoff from an X error. The class name is all that is kept."""
    if status == 429:
        until = reset_at or (now + timedelta(minutes=15))
        kind = "rate"
        credits_value = credits
    elif status in {402, 403}:
        until = now + timedelta(hours=1)
        kind = "credits"
        credits_value = 0 if credits is None else credits
    elif status == 401:
        until = now + timedelta(minutes=30)
        kind = "auth"
        credits_value = credits
    else:
        until = now + timedelta(minutes=15)
        kind = "http"
        credits_value = credits
    note_limits(
        session,
        now,
        credits_remaining=credits_value,
        rate_remaining=rate,
        rate_reset_at=reset_at,
        error_class=kind,
        backoff_until=until,
    )
    return kind


def record_post_failure(session: Session, item_id: UUID, error_class: str, now: datetime) -> None:
    session.add(
        XPostAudit(
            item_id=item_id,
            outcome="failed",
            error_class=error_class[:40],
            created_at=now,
        )
    )


def record_post_success(session: Session, row: XItem, tweet_id: str, now: datetime) -> None:
    row.status = "posted"
    row.decided_at = now
    row.posted_tweet_id = tweet_id
    session.add(XPostAudit(item_id=row.id, outcome="posted", tweet_id=tweet_id, created_at=now))
    record_event(
        session,
        kind="system",
        title="Posted to X",
        body=f"Tweet {tweet_id}.",
        owner=DEFAULT_OWNER,
    )
