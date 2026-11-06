"""Sprint 7. X stays behind the flag. A post leaves only after confirm. hearthis is cached."""

import hashlib
import base64
import json
import logging
from datetime import timedelta
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

import httpx
from cryptography.fernet import Fernet
from sqlalchemy import func, select

from agent_fakes import london
from organiser.agent.functions import RunContext, dispatch
from organiser.config import get_settings
from organiser.models import AgentRun, Event, XConnection, XCursor, XItem, XOauthPending, XPostAudit
from organiser.routes.hooks import clear_replay_cache
from organiser.services.playlist import set_transport as set_playlist_transport
from organiser.x.client import set_transport
from organiser.x.crypto import open_sealed

TOKEN_KEY = Fernet.generate_key().decode()
REFRESH = "refresh-token-value"
ACCESS = "access-token-value"
CODE = "code-from-x"
SECRET = "x-relay-secret"


def _enable(monkeypatch, **extra):
    monkeypatch.setenv("X_ENABLED", "true")
    monkeypatch.setenv("X_CLIENT_ID", "x-client")
    monkeypatch.setenv("X_CLIENT_SECRET", "x-secret-not-real")
    monkeypatch.setenv("X_REDIRECT_URI", "https://organiser.apidiscoverysolution.uk/x/callback")
    monkeypatch.setenv("X_TOKEN_KEY", TOKEN_KEY)
    monkeypatch.setenv("X_POLL_MINUTES", "30")
    for key, value in extra.items():
        monkeypatch.setenv(key, value)
    get_settings.cache_clear()


class XApi:
    def __init__(self):
        self.calls: list[str] = []
        self.bookmarks: list[dict] = []
        self.search: list[dict] = []
        self.users = [{"id": "7", "username": "housebin"}]
        self.fail: int | None = None
        self.revoke_status = 200
        self.revoked = ""
        self.posted: list[dict] = []
        self.queries: list[str] = []
        self.since: list[str] = []
        self.reset = "1893456000"
        self.credits = "120"
        self.rate = "45"

    def headers(self) -> dict[str, str]:
        return {
            "x-credits-remaining": self.credits,
            "x-rate-limit-remaining": self.rate,
            "x-rate-limit-reset": self.reset,
        }

    def handler(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        self.calls.append(f"{request.method} {path}")
        if path.endswith("/oauth2/revoke"):
            self.revoked = request.content.decode()
            return httpx.Response(self.revoke_status, headers=self.headers())
        if self.fail and not path.endswith("/oauth2/token") and not path.endswith("/users/me"):
            return httpx.Response(self.fail, headers=self.headers())
        if path.endswith("/oauth2/token"):
            return httpx.Response(
                200,
                json={
                    "access_token": ACCESS,
                    "refresh_token": REFRESH,
                    "expires_in": 7200,
                    "scope": "tweet.read users.read bookmark.read tweet.write offline.access",
                },
            )
        if path.endswith("/users/me"):
            return httpx.Response(200, json={"data": {"id": "42", "username": "nickhome"}})
        if path.endswith("/bookmarks"):
            newest = self.bookmarks[0]["id"] if self.bookmarks else None
            return httpx.Response(
                200,
                json={
                    "data": self.bookmarks,
                    "includes": {"users": self.users},
                    "meta": {"newest_id": newest, "result_count": len(self.bookmarks)},
                },
                headers=self.headers(),
            )
        if path.endswith("/tweets/search/recent"):
            self.queries.append(request.url.params.get("query") or "")
            if request.url.params.get("since_id"):
                self.since.append(request.url.params["since_id"])
            newest = self.search[0]["id"] if self.search else None
            return httpx.Response(
                200,
                json={
                    "data": self.search,
                    "includes": {"users": self.users},
                    "meta": {"newest_id": newest, "result_count": len(self.search)},
                },
                headers=self.headers(),
            )
        if path == "/2/tweets" and request.method == "POST":
            self.posted.append(json.loads(request.content))
            return httpx.Response(201, json={"data": {"id": "9001"}}, headers=self.headers())
        return httpx.Response(404)


def _install(api: XApi) -> None:
    set_transport(httpx.MockTransport(api.handler))


def _connect(client, db):
    started = client.post("/x/connect")
    assert started.status_code == 200, started.text
    url = started.json()["authorize_url"]
    state = parse_qs(urlparse(url).query)["state"][0]
    callback = client.get("/x/callback", params={"code": CODE, "state": state}, follow_redirects=False)
    assert callback.status_code == 303
    assert callback.headers["location"].endswith("/?x=connected")
    assert CODE not in callback.headers["location"]
    db.expire_all()
    return url


def _sign(raw: bytes, stamp: int, secret: str = SECRET) -> str:
    import hmac

    return hmac.new(secret.encode(), f"{stamp}.".encode() + raw, hashlib.sha256).hexdigest()


def test_x_is_off_until_the_flag_is_set(client, monkeypatch):
    assert client.get("/x/status").json()["enabled"] is False
    assert client.post("/x/connect").status_code == 404
    assert client.post("/x/poll").json()["reason"] == "off"
    assert client.get("/system/status").json()["x"]["enabled"] is False
    monkeypatch.setenv("X_CLIENT_SECRET", "x-secret-not-real")
    monkeypatch.setenv("X_TOKEN_KEY", TOKEN_KEY)
    get_settings.cache_clear()
    try:
        assert "x-secret-not-real" not in repr(get_settings())
        assert TOKEN_KEY not in repr(get_settings())
    finally:
        get_settings.cache_clear()


def test_connect_seals_the_refresh_token_and_disconnect_revokes_it(client, db, monkeypatch, caplog):
    _enable(monkeypatch)
    api = XApi()
    _install(api)
    try:
        with caplog.at_level(logging.DEBUG):
            url = _connect(client, db)
        query = parse_qs(urlparse(url).query)
        assert query["code_challenge_method"] == ["S256"]
        assert set(query["scope"][0].split()) == {
            "tweet.read",
            "users.read",
            "bookmark.read",
            "tweet.write",
            "offline.access",
        }
        assert query["redirect_uri"] == ["https://organiser.apidiscoverysolution.uk/x/callback"]
        assert "x-secret-not-real" not in url
        assert REFRESH not in url
        row = db.scalar(select(XConnection))
        assert row.username == "nickhome"
        assert REFRESH not in row.refresh_token
        assert ACCESS not in row.access_token
        assert open_sealed(TOKEN_KEY, row.refresh_token) == REFRESH
        pending = db.get(XOauthPending, query["state"][0])
        assert pending is None
        verifier_row = db.scalars(select(XOauthPending)).all()
        assert verifier_row == []
        assert REFRESH not in caplog.text
        assert ACCESS not in caplog.text
        assert CODE not in caplog.text
        assert TOKEN_KEY not in caplog.text

        status = client.get("/x/status").json()
        assert status["connected"] is True
        assert status["username"] == "nickhome"
        assert REFRESH not in json.dumps(status)

        with caplog.at_level(logging.DEBUG):
            gone = client.post("/x/disconnect")
        assert gone.status_code == 200
        assert gone.json()["connected"] is False
        assert REFRESH not in gone.text
        assert REFRESH in api.revoked
        assert "x-secret-not-real" not in api.revoked
        db.expire_all()
        assert db.scalar(select(XConnection)) is None
        assert REFRESH not in caplog.text
    finally:
        get_settings.cache_clear()


def test_disconnect_keeps_the_token_when_revoke_fails(client, db, monkeypatch):
    _enable(monkeypatch)
    api = XApi()
    api.revoke_status = 503
    _install(api)
    try:
        _connect(client, db)
        refused = client.post("/x/disconnect")
        assert refused.status_code == 502
        assert REFRESH not in refused.text
        db.expire_all()
        assert db.scalar(select(XConnection)) is not None
    finally:
        get_settings.cache_clear()


def test_pkce_challenge_matches_the_sealed_verifier(client, db, monkeypatch):
    _enable(monkeypatch)
    api = XApi()
    _install(api)
    try:
        started = client.post("/x/connect")
        url = started.json()["authorize_url"]
        query = parse_qs(urlparse(url).query)
        db.expire_all()
        pending = db.get(XOauthPending, query["state"][0])
        verifier = open_sealed(TOKEN_KEY, pending.verifier)
        digest = hashlib.sha256(verifier.encode()).digest()
        challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
        assert query["code_challenge"] == [challenge]
    finally:
        get_settings.cache_clear()


def _ctx(db, now, max_proposals=3):
    run = AgentRun(trigger="feed", window_key=f"test:{uuid4()}", status="running", started_at=now)
    db.add(run)
    db.flush()
    return RunContext(
        session=db,
        now=now,
        tz_name="Europe/London",
        run=run,
        origin="feed",
        rule="feed",
        label="From your note",
        max_proposals=max_proposals,
    )


def test_poll_caches_since_id_and_feeds_cards_and_the_brief(client, db, house_clock, monkeypatch, caplog):
    house_clock["now"] = london(2026, 11, 2, 8, 0)
    _enable(monkeypatch)
    api = XApi()
    api.bookmarks = [
        {"id": "100", "text": "Put the bins out tonight", "author_id": "7"},
        {"id": "50", "text": "Email the colleague about the rota", "author_id": "7"},
    ]
    api.search = [{"id": "80", "text": "Council collection moved to Friday", "author_id": "7"}]
    _install(api)
    try:
        _connect(client, db)
        added = client.post("/x/watches", json={"kind": "keyword", "value": "bins"})
        assert added.status_code == 200
        account = client.post("/x/watches", json={"kind": "account", "value": "@HouseBin"})
        assert account.json()["value"] == "housebin"
        refused = client.post("/x/watches", json={"kind": "keyword", "value": "colleague"})
        assert refused.status_code == 422
        with caplog.at_level(logging.DEBUG):
            first = client.post("/x/poll")
        assert first.json() == {"ran": True, "reason": "polled"}
        assert ACCESS not in caplog.text
        assert REFRESH not in caplog.text
        cards = client.get("/x/items").json()["items"]
        summaries = [item["summary"] for item in cards]
        assert "Put the bins out tonight" in summaries
        assert "Council collection moved to Friday" in summaries
        assert all("colleague" not in item["summary"] for item in cards)
        kinds = {item["kind"] for item in cards}
        assert kinds == {"bookmark", "watch_match"}
        brief = client.get("/brief/morning").json()
        section = next(item for item in brief["sections"] if item["key"] == "x")
        assert "bins" in section["summary"] or "from X" in section["summary"]
        assert "colleague" not in json.dumps(section)
        calls = len(api.calls)
        cached = client.post("/x/poll")
        assert cached.json()["reason"] == "cached"
        assert len(api.calls) == calls
        status = client.get("/system/status").json()["x"]
        assert status["credits_remaining"] == 120
        assert status["rate_remaining"] == 45
        assert status["backing_off"] is False

        house_clock["now"] = london(2026, 11, 2, 8, 31)
        api.bookmarks = [
            {"id": "110", "text": "Filters are by the boiler", "author_id": "7"},
            {"id": "100", "text": "Put the bins out tonight", "author_id": "7"},
        ]
        api.search = [{"id": "80", "text": "Council collection moved to Friday", "author_id": "7"}]
        again = client.post("/x/poll")
        assert again.json()["reason"] == "polled"
        assert api.since  # recent search was given the cursor
        db.expire_all()
        titles = [row.text for row in db.scalars(select(XItem))]
        assert titles.count("Put the bins out tonight") == 1
        assert "Filters are by the boiler" in titles
        cursor = db.get(XCursor, "bookmarks")
        assert cursor.since_id == "110"
    finally:
        get_settings.cache_clear()


def test_a_rate_limit_backs_off_without_another_call(client, db, house_clock, monkeypatch):
    house_clock["now"] = london(2026, 11, 2, 8, 0)
    _enable(monkeypatch)
    api = XApi()
    api.reset = str(int(house_clock["now"].timestamp()) + 900)
    _install(api)
    try:
        _connect(client, db)
        api.fail = 429
        limited = client.post("/x/poll")
        assert limited.json()["reason"] == "limited"
        calls = len(api.calls)
        status = client.get("/system/status").json()["x"]
        assert status["backing_off"] is True
        assert status["attention"] == "rate"
        house_clock["now"] = london(2026, 11, 2, 8, 5)
        assert client.post("/x/poll").json()["reason"] == "backoff"
        assert len(api.calls) == calls
    finally:
        get_settings.cache_clear()


def test_draft_posts_only_after_confirm_and_expires(client, db, house_clock, monkeypatch):
    now = london(2026, 11, 2, 8, 0)
    house_clock["now"] = now
    _enable(monkeypatch)
    api = XApi()
    _install(api)
    try:
        _connect(client, db)
        refused = dispatch(_ctx(db, now), "propose_draft", {"text": "Email the colleague", "reason": "Work."})
        assert refused["ok"] is False
        assert "house log" in refused["error"]
        context = _ctx(db, now, max_proposals=1)
        first = dispatch(context, "propose_draft", {"text": "The boiler filter is in the hall", "reason": "Say it once."})
        assert first["ok"] is True
        second = dispatch(context, "propose_draft", {"text": "Milk is on the list", "reason": "Already said."})
        assert second["ok"] is False
        db.commit()

        quiet = client.post(f"/x/items/{first['draft_id']}/post", json={})
        assert quiet.status_code == 422
        assert api.posted == []
        missing = client.post(f"/x/items/{first['draft_id']}/post", json={"confirm": False})
        assert missing.status_code == 422
        assert api.posted == []

        posted = client.post(f"/x/items/{first['draft_id']}/post", json={"confirm": True})
        assert posted.status_code == 200, posted.text
        assert posted.json()["tweet_id"] == "9001"
        assert posted.json()["status"] == "posted"
        assert ACCESS not in posted.text
        assert api.posted == [{"text": "The boiler filter is in the hall"}]
        db.expire_all()
        audit = db.scalars(select(XPostAudit)).all()
        assert [row.outcome for row in audit] == ["posted"]
        assert audit[0].tweet_id == "9001"
        titles = [row.title for row in db.scalars(select(Event))]
        assert "Posted to X" in titles

        again = client.post(f"/x/items/{first['draft_id']}/post", json={"confirm": True})
        assert again.status_code == 409
        assert api.posted == [{"text": "The boiler filter is in the hall"}]

        later = dispatch(_ctx(db, now), "propose_draft", {"text": "Leave the key under the pot", "reason": "Home tonight."})
        assert later["ok"] is True
        db.commit()
        house_clock["now"] = now + timedelta(days=8)
        listed = client.get("/x/items").json()["items"]
        assert all(item["summary"] != "Leave the key under the pot" for item in listed)
        db.expire_all()
        expired = db.scalar(select(XItem).where(XItem.text == "Leave the key under the pot"))
        assert expired.status == "expired"
    finally:
        get_settings.cache_clear()


def test_apply_keeps_a_bookmark_in_the_log_and_does_not_post(client, db, house_clock, monkeypatch):
    house_clock["now"] = london(2026, 11, 2, 8, 0)
    _enable(monkeypatch)
    api = XApi()
    api.bookmarks = [{"id": "100", "text": "Put the bins out tonight", "author_id": "7"}]
    _install(api)
    try:
        _connect(client, db)
        assert client.post("/x/poll").json()["ran"] is True
        card = client.get("/x/items").json()["items"][0]
        applied = client.post(f"/x/items/{card['id']}/apply")
        assert applied.status_code == 200
        assert applied.json()["status"] == "applied"
        assert api.posted == []
        db.expire_all()
        bodies = [row.body for row in db.scalars(select(Event))]
        assert any(body and "Nothing was sent." in body for body in bodies)
        assert client.get("/x/items").json()["items"] == []
    finally:
        get_settings.cache_clear()


def test_webhook_x_events_use_the_same_pipeline(client, db, house_clock, monkeypatch):
    house_clock["now"] = london(2026, 11, 6, 8, 0)
    _enable(monkeypatch, WEBHOOK_SECRET_BANTO_X=SECRET)
    clear_replay_cache()
    raw = json.dumps(
        {
            "event": "x.bookmark",
            "id": "55",
            "text": "The library book is due",
            "author": "housebin",
            "url": "https://x.com/housebin/status/55",
        }
    ).encode()
    outside = json.dumps(
        {"event": "x.bookmark", "id": "56", "text": "Guest list for the colleague", "author": "housebin"}
    ).encode()
    try:
        closed = client.post("/hooks/banto_x", json={"event": "x.bookmark", "id": "1", "text": "hi"})
        # Secret is set, but this body is not signed.
        assert closed.status_code == 401

        stamp = int(house_clock["now"].timestamp())
        opened = client.post(
            "/hooks/banto_x",
            content=raw,
            headers={
                "content-type": "application/json",
                "x-organiser-timestamp": str(stamp),
                "x-organiser-signature": _sign(raw, stamp),
            },
        )
        assert opened.status_code == 200, opened.text
        cards = client.get("/x/items").json()["items"]
        assert cards[0]["summary"] == "The library book is due"
        assert cards[0]["kind"] == "bookmark"

        refused = client.post(
            "/hooks/banto_x",
            content=outside,
            headers={
                "content-type": "application/json",
                "x-organiser-timestamp": str(stamp + 1),
                "x-organiser-signature": _sign(outside, stamp + 1),
            },
        )
        assert refused.status_code == 422
        db.expire_all()
        assert db.scalar(select(func.count()).select_from(XItem)) == 1

        monkeypatch.setenv("X_ENABLED", "false")
        get_settings.cache_clear()
        draft = json.dumps({"event": "x.draft", "text": "A quiet line"}).encode()
        disabled = client.post(
            "/hooks/banto_x",
            content=draft,
            headers={
                "content-type": "application/json",
                "x-organiser-timestamp": str(stamp + 2),
                "x-organiser-signature": _sign(draft, stamp + 2),
            },
        )
        assert disabled.status_code == 503
        db.expire_all()
        assert db.scalar(select(func.count()).select_from(XItem)) == 1
    finally:
        get_settings.cache_clear()
        clear_replay_cache()


def test_paused_house_does_not_poll_or_post(client, db, house_clock, monkeypatch):
    house_clock["now"] = london(2026, 11, 2, 8, 0)
    _enable(monkeypatch)
    api = XApi()
    _install(api)
    try:
        _connect(client, db)
        context = _ctx(db, house_clock["now"])
        made = dispatch(context, "propose_draft", {"text": "Bins tonight", "reason": "Due tonight."})
        db.commit()
        assert client.post("/system/pause").status_code == 200
        calls = len(api.calls)
        assert client.post("/x/poll").json()["reason"] == "paused"
        assert len(api.calls) == calls
        refused = client.post(f"/x/items/{made['draft_id']}/post", json={"confirm": True})
        assert refused.status_code == 409
        assert api.posted == []
    finally:
        get_settings.cache_clear()


def test_hearthis_is_cached_for_an_hour_and_quiet_when_offline(client, house_clock, monkeypatch):
    house_clock["now"] = london(2026, 11, 2, 8, 0)
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        assert request.url.params["type"] == "tracks"
        assert request.url.params["count"] == "10"
        assert "stream" not in str(request.url)
        return httpx.Response(
            200,
            json=[
                {
                    "title": "Morning Haze",
                    "genre": "Dub",
                    "permalink_url": "https://hearthis.at/chlorophil/morning-haze/",
                    "thumb": "https://img.hearthis.at/art/thumb.jpg",
                    "stream_url": "https://hearthis.at/secret-stream",
                    "private": "0",
                }
            ],
        )

    set_playlist_transport(httpx.MockTransport(handler))
    assert client.get("/playlist").json()["shown"] is False
    assert calls["n"] == 0
    monkeypatch.setenv("PLAYLIST_SOURCE", "hearthis")
    monkeypatch.setenv("HEARTHIS_PROFILE", "chlorophil")
    get_settings.cache_clear()
    try:
        first = client.get("/playlist").json()
        assert first["title"] == "Morning Haze"
        assert first["genre"] == "Dub"
        assert first["artwork_url"].startswith("https://img.hearthis.at/")
        assert first["permalink_url"].startswith("https://hearthis.at/")
        assert first["offline"] is False
        assert "stream" not in json.dumps(first)
        assert calls["n"] == 1
        assert client.get("/playlist").json()["title"] == "Morning Haze"
        assert calls["n"] == 1

        house_clock["now"] = london(2026, 11, 2, 10, 0)
        assert client.get("/playlist").json()["title"] == "Morning Haze"
        assert calls["n"] == 2

        def offline(request: httpx.Request) -> httpx.Response:
            calls["n"] += 1
            raise httpx.ConnectError("offline")

        set_playlist_transport(httpx.MockTransport(offline))
        house_clock["now"] = london(2026, 11, 2, 12, 0)
        stale = client.get("/playlist").json()
        assert stale["offline"] is True
        assert stale["title"] == "Morning Haze"
        assert stale["shown"] is True

        from organiser.services.playlist import clear_cache

        clear_cache()
        quiet = client.get("/playlist").json()
        assert quiet["shown"] is True
        assert quiet["offline"] is True
        assert quiet["title"] is None

        monkeypatch.setenv("SHOW_PLAYLIST", "false")
        get_settings.cache_clear()
        hidden = client.get("/playlist").json()
        assert hidden["shown"] is False
    finally:
        get_settings.cache_clear()
