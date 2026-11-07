"""Bookmark poll, watch search, and the one confirmed post."""

from __future__ import annotations

from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy.orm import Session

from organiser.agent.runner import outside_home
from organiser.config import Settings
from organiser.models import XItem
from organiser.services.system import ensure_system_state
from organiser.x.client import XHttp, XUnavailable
from organiser.x.oauth import fresh_access, newest_id, open_client, parse_tweets
from organiser.x.store import (
    XRejected,
    apply_http_error,
    cursor_since,
    ensure_meter,
    note_limits,
    record_post_failure,
    record_post_success,
    remember_external,
    save_cursor,
    search_query,
    watches,
)


def _keep(session: Session, limits, now: datetime) -> None:
    note_limits(
        session,
        now,
        credits_remaining=limits.credits_remaining,
        rate_remaining=limits.rate_remaining,
        rate_reset_at=limits.rate_reset_at,
    )


def _store_page(session: Session, *, kind: str, body: dict, since_id: str | None, cursor: str, now: datetime) -> str | None:
    newest = newest_id(body)
    seen: list[str] = []
    for tweet in parse_tweets(body):
        seen.append(tweet["id"])
        remember_external(
            session,
            kind=kind,
            external_id=tweet["id"],
            text=tweet["text"],
            author=tweet["author"],
            url=None,
            source="poll",
            now=now,
            strict=False,
            since_id=since_id,
        )
    if newest is None and seen:
        newest = max(seen, key=lambda item: int(item))
    save_cursor(session, cursor, newest, now)
    return newest


def poll(session: Session, settings: Settings, now: datetime) -> dict:
    """Read bookmarks and watches when the interval has elapsed. Nothing is posted."""
    if not settings.x_enabled:
        return {"ran": False, "reason": "off"}
    if ensure_system_state(session).paused:
        return {"ran": False, "reason": "paused"}
    from organiser.models import XConnection

    connection = session.get(XConnection, 1)
    if connection is None:
        return {"ran": False, "reason": "disconnected"}
    meter = ensure_meter(session, now)
    if meter.poll_paused:
        return {"ran": False, "reason": "poll_paused"}
    if meter.backoff_until and meter.backoff_until > now:
        return {"ran": False, "reason": "backoff"}
    if meter.rate_remaining == 0 and meter.rate_reset_at and meter.rate_reset_at > now:
        meter.backoff_until = meter.rate_reset_at
        meter.updated_at = now
        return {"ran": False, "reason": "backoff"}
    interval = timedelta(minutes=settings.poll_interval_minutes)
    if meter.last_poll_at and now - meter.last_poll_at < interval:
        return {"ran": False, "reason": "cached"}

    note_limits(session, now, polled=True)
    try:
        with open_client(settings) as client:
            access = fresh_access(session, settings, client, now)
            body, limits = client.bookmarks(access, connection.x_user_id)
            _keep(session, limits, now)
            if limits.credits_remaining == 0:
                note_limits(
                    session,
                    now,
                    credits_remaining=0,
                    error_class="credits",
                    backoff_until=now + timedelta(hours=1),
                )
                return {"ran": True, "reason": "credits"}
            _store_page(
                session,
                kind="bookmark",
                body=body,
                since_id=cursor_since(session, "bookmarks"),
                cursor="bookmarks",
                now=now,
            )
            for watch in watches(session):
                if outside_home(watch.value):
                    continue
                name = f"watch:{watch.id}"
                since = cursor_since(session, name)
                found, limits = client.search_recent(access, search_query(watch.kind, watch.value), since)
                _keep(session, limits, now)
                _store_page(session, kind="watch_match", body=found, since_id=since, cursor=name, now=now)
                if limits.credits_remaining == 0 or limits.rate_remaining == 0:
                    break
    except XHttp as exc:
        apply_http_error(
            session,
            exc.status,
            now,
            credits=exc.limits.credits_remaining,
            rate=exc.limits.rate_remaining,
            reset_at=exc.limits.rate_reset_at,
        )
        return {"ran": False, "reason": "limited"}
    except XUnavailable:
        note_limits(session, now, error_class="unreachable", backoff_until=now + timedelta(minutes=15))
        return {"ran": False, "reason": "unreachable"}
    except XRejected:
        return {"ran": False, "reason": "disconnected"}
    return {"ran": True, "reason": "polled"}


def post_draft(session: Session, settings: Settings, item_id: UUID, now: datetime, *, confirm: bool) -> XItem:
    """Send one draft. The caller has to pass confirm, and this still checks it."""
    if not confirm:
        raise XRejected("Confirm the post.", 422)
    if not settings.x_enabled:
        raise XRejected("X is off.", 404)
    if ensure_system_state(session).paused:
        raise XRejected("The house is paused. Nothing was posted.", 409)
    row = session.get(XItem, item_id, with_for_update=True)
    if row is None:
        raise XRejected("That card is not here.", 404)
    if row.kind != "draft" or row.status != "pending":
        raise XRejected("That draft is not waiting.", 409)
    if row.expires_at is not None and row.expires_at <= now:
        row.status = "expired"
        row.decided_at = now
        raise XRejected("That draft has expired.", 409, persist=True)
    if outside_home(row.text):
        row.status = "dismissed"
        row.decided_at = now
        raise XRejected("Not for the house log.", 422, persist=True)
    meter = ensure_meter(session, now)
    if meter.backoff_until and meter.backoff_until > now:
        if meter.credits_remaining == 0:
            raise XRejected("X credits are spent. Nothing was posted.", 429)
        raise XRejected("X is backing off. Nothing was posted.", 429)
    try:
        with open_client(settings) as client:
            access = fresh_access(session, settings, client, now)
            tweet_id, limits = client.post_tweet(access, row.text)
        _keep(session, limits, now)
    except XHttp as exc:
        kind = apply_http_error(
            session,
            exc.status,
            now,
            credits=exc.limits.credits_remaining,
            rate=exc.limits.rate_remaining,
            reset_at=exc.limits.rate_reset_at,
        )
        record_post_failure(session, row.id, kind, now)
        raise XRejected("X did not take the post. Nothing was posted.", 502, persist=True) from exc
    except XUnavailable:
        note_limits(session, now, error_class="unreachable", backoff_until=now + timedelta(minutes=15))
        record_post_failure(session, row.id, "unreachable", now)
        raise XRejected("X could not be reached. Nothing was posted.", 502, persist=True) from None
    except XRejected:
        raise
    record_post_success(session, row, tweet_id, now)
    return row
