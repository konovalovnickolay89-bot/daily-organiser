"""OAuth 2.0 with PKCE for Nick's own X app. Refresh tokens are sealed at rest."""

from __future__ import annotations

import hashlib
import base64
import secrets
from datetime import datetime, timedelta
from urllib.parse import urlparse

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from organiser.config import Settings
from organiser.models import XConnection, XOauthPending
from organiser.x.client import SCOPES, TokenBundle, XClient, XHttp, XUnavailable, authorize_url
from organiser.x.crypto import TokenKeyError, key_ok, open_sealed, seal
from organiser.x.store import XRejected

PENDING_MINUTES = 10


def setup_ok(settings: Settings) -> bool:
    if not settings.x_enabled:
        return False
    client_id = settings.x_client_id.get_secret_value().strip()
    secret = settings.x_client_secret.get_secret_value().strip()
    token_key = settings.x_token_key.get_secret_value()
    return bool(client_id and secret and key_ok(token_key) and _redirect_ok(settings.x_redirect_uri))


def _redirect_ok(uri: str) -> bool:
    parsed = urlparse(uri.strip())
    if not parsed.netloc or parsed.params or parsed.query or parsed.fragment:
        return False
    if parsed.scheme == "https":
        return True
    return parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1"}


def _key(settings: Settings) -> str:
    return settings.x_token_key.get_secret_value()


def open_client(settings: Settings) -> XClient:
    return XClient(
        settings.x_client_id.get_secret_value().strip(),
        settings.x_client_secret.get_secret_value().strip(),
        settings.x_redirect_uri.strip(),
    )


def _challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def _purge(session: Session, now: datetime) -> None:
    cutoff = now - timedelta(minutes=PENDING_MINUTES)
    session.execute(delete(XOauthPending).where(XOauthPending.created_at < cutoff))


def begin(session: Session, settings: Settings, now: datetime) -> str:
    if not settings.x_enabled:
        raise XRejected("X is off.", 404)
    if not setup_ok(settings):
        raise XRejected("X is not configured.", 503)
    if session.get(XConnection, 1) is not None:
        raise XRejected("X is already connected.", 409)
    _purge(session, now)
    verifier = secrets.token_urlsafe(64)
    state = secrets.token_urlsafe(24)
    try:
        hidden = seal(_key(settings), verifier)
    except TokenKeyError as exc:
        raise XRejected("X is not configured.", 503) from exc
    session.add(XOauthPending(state=state, verifier=hidden, created_at=now))
    session.flush()
    return authorize_url(
        settings.x_client_id.get_secret_value().strip(),
        settings.x_redirect_uri.strip(),
        state,
        _challenge(verifier),
    )


def take_verifier(session: Session, settings: Settings, state: str, now: datetime) -> str:
    if not state:
        raise XRejected("The X connection expired. Try again.", 400)
    pending = session.get(XOauthPending, state)
    if pending is None or now - pending.created_at > timedelta(minutes=PENDING_MINUTES):
        if pending is not None:
            session.delete(pending)
        raise XRejected("The X connection expired. Try again.", 400)
    try:
        verifier = open_sealed(_key(settings), pending.verifier)
    except TokenKeyError as exc:
        session.delete(pending)
        raise XRejected("X is not configured.", 503) from exc
    session.delete(pending)
    session.flush()
    return verifier


def save_connection(
    session: Session,
    settings: Settings,
    bundle: TokenBundle,
    user_id: str,
    username: str,
    now: datetime,
) -> XConnection:
    try:
        access = seal(_key(settings), bundle.access_token)
        refresh = seal(_key(settings), bundle.refresh_token)
    except TokenKeyError as exc:
        raise XRejected("X is not configured.", 503) from exc
    row = session.get(XConnection, 1)
    if row is None:
        row = XConnection(id=1, connected_at=now, x_user_id=user_id, username=username[:15])
        session.add(row)
    row.x_user_id = user_id
    row.username = username[:15]
    row.access_token = access
    row.refresh_token = refresh
    row.access_expires_at = now + timedelta(seconds=max(30, bundle.expires_in - 30))
    row.scopes = bundle.scope[:200] or " ".join(SCOPES)
    row.updated_at = now
    session.flush()
    return row


def fresh_access(session: Session, settings: Settings, client: XClient, now: datetime) -> str:
    """The access token for one call. Refresh when it is about to lapse, and seal the new pair."""
    row = session.get(XConnection, 1)
    if row is None:
        raise XRejected("X is not connected.", 409)
    try:
        if row.access_expires_at > now + timedelta(seconds=60):
            return open_sealed(_key(settings), row.access_token)
        refresh = open_sealed(_key(settings), row.refresh_token)
    except TokenKeyError as exc:
        raise XRejected("X is not configured.", 503) from exc
    bundle, _limits = client.refresh(refresh)
    save_connection(session, settings, bundle, row.x_user_id, row.username, now)
    return bundle.access_token


def disconnect(session: Session, settings: Settings) -> None:
    if not settings.x_enabled:
        raise XRejected("X is off.", 404)
    row = session.get(XConnection, 1)
    if row is None:
        raise XRejected("X is not connected.", 404)
    try:
        refresh = open_sealed(_key(settings), row.refresh_token)
    except TokenKeyError as exc:
        raise XRejected("X is not configured.", 503) from exc
    try:
        with open_client(settings) as client:
            client.revoke(refresh)
    except XHttp as exc:
        if exc.status not in {400, 401, 404}:
            raise XRejected("X did not revoke the token. It is still stored.", 502) from exc
    except XUnavailable as exc:
        raise XRejected("X could not be reached. The token is still stored.", 502) from exc
    session.delete(row)
    session.execute(delete(XOauthPending))
    session.flush()


def status_view(session: Session, settings: Settings, now: datetime) -> dict:
    row = session.get(XConnection, 1) if settings.x_enabled else None
    from organiser.x.store import reading_view, watches

    listed = watches(session) if settings.x_enabled else []
    body = {
        "enabled": settings.x_enabled,
        "configured": setup_ok(settings),
        "connected": row is not None,
        "username": row.username if row is not None else None,
        "watches": [{"id": item.id, "kind": item.kind, "value": item.value} for item in listed],
        "poll_interval_minutes": settings.poll_interval_minutes if settings.x_enabled else None,
    }
    body.update(reading_view(session, enabled=settings.x_enabled, now=now))
    return body


def exchange_and_store(session: Session, settings: Settings, code: str, verifier: str, now: datetime) -> XConnection:
    with open_client(settings) as client:
        bundle, _limits = client.exchange(code, verifier)
        user, limits = client.me(bundle.access_token)
    from organiser.x.store import note_limits

    note_limits(
        session,
        now,
        credits_remaining=limits.credits_remaining,
        rate_remaining=limits.rate_remaining,
        rate_reset_at=limits.rate_reset_at,
    )
    return save_connection(session, settings, bundle, user.id, user.username, now)


def newest_id(body: dict) -> str | None:
    meta = body.get("meta")
    if isinstance(meta, dict) and str(meta.get("newest_id") or "").isdigit():
        return str(meta["newest_id"])
    return None


def parse_tweets(body: dict) -> list[dict]:
    data = body.get("data")
    if not isinstance(data, list):
        return []
    users: dict[str, str] = {}
    includes = body.get("includes")
    if isinstance(includes, dict):
        listed = includes.get("users")
        if isinstance(listed, list):
            for user in listed:
                if isinstance(user, dict) and user.get("id"):
                    users[str(user["id"])] = str(user.get("username") or "")
    rows: list[dict] = []
    for tweet in data:
        if not isinstance(tweet, dict):
            continue
        tweet_id = str(tweet.get("id") or "")
        text = tweet.get("text")
        if not tweet_id.isdigit() or not isinstance(text, str):
            continue
        author = users.get(str(tweet.get("author_id") or "")) or None
        rows.append({"id": tweet_id, "text": text, "author": author})
    return rows


def pending_states(session: Session) -> list[XOauthPending]:
    return list(session.scalars(select(XOauthPending)).all())
