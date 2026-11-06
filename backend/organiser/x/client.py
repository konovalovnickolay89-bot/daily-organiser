"""Calls to Nick's X app. A token is a header for one request. It is not logged."""

from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import urlencode

import httpx

AUTHORIZE_URL = "https://twitter.com/i/oauth2/authorize"
TOKEN_URL = "https://api.x.com/2/oauth2/token"
REVOKE_URL = "https://api.x.com/2/oauth2/revoke"
API = "https://api.x.com/2"

SCOPES = ("tweet.read", "users.read", "bookmark.read", "tweet.write", "offline.access")

_transport: httpx.BaseTransport | None = None


def set_transport(transport: httpx.BaseTransport | None) -> None:
    global _transport
    _transport = transport


@dataclass(frozen=True)
class Limits:
    credits_remaining: int | None = None
    rate_remaining: int | None = None
    rate_reset_at: datetime | None = None


class XHttp(Exception):
    """X answered with an error. The message is the status, never the body."""

    def __init__(self, status: int, limits: Limits):
        self.status = status
        self.limits = limits
        super().__init__(f"X answered {status}")


class XUnavailable(Exception):
    def __init__(self) -> None:
        super().__init__("X could not be reached")


@dataclass(frozen=True)
class TokenBundle:
    access_token: str
    refresh_token: str
    expires_in: int
    scope: str


@dataclass(frozen=True)
class XUser:
    id: str
    username: str


def authorize_url(client_id: str, redirect_uri: str, state: str, challenge: str) -> str:
    query = urlencode(
        {
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "scope": " ".join(SCOPES),
            "state": state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        }
    )
    return f"{AUTHORIZE_URL}?{query}"


def _header_int(headers: httpx.Headers, *names: str) -> int | None:
    for name in names:
        raw = headers.get(name)
        if raw is None or not str(raw).strip():
            continue
        try:
            return int(str(raw).strip())
        except ValueError:
            continue
    return None


def read_limits(headers: httpx.Headers) -> Limits:
    reset = _header_int(headers, "x-rate-limit-reset")
    when = datetime.fromtimestamp(reset, timezone.utc) if reset else None
    return Limits(
        credits_remaining=_header_int(
            headers,
            "x-credits-remaining",
            "x-credit-limit-remaining",
            "x-user-limit-24hour-remaining",
        ),
        rate_remaining=_header_int(headers, "x-rate-limit-remaining"),
        rate_reset_at=when,
    )


def _bundle(body: dict, fallback_refresh: str | None = None) -> TokenBundle:
    access = body.get("access_token")
    refresh = body.get("refresh_token") or fallback_refresh
    if not isinstance(access, str) or not access or not isinstance(refresh, str) or not refresh:
        raise XHttp(502, Limits())
    try:
        expires_in = int(body.get("expires_in") or 7200)
    except (TypeError, ValueError):
        expires_in = 7200
    scope = body.get("scope") if isinstance(body.get("scope"), str) else " ".join(SCOPES)
    return TokenBundle(access_token=access, refresh_token=refresh, expires_in=max(60, expires_in), scope=scope[:200])


class XClient:
    def __init__(self, client_id: str, client_secret: str, redirect_uri: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self._http = httpx.Client(timeout=10.0, follow_redirects=False, transport=_transport)

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> XClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def _basic(self) -> str:
        raw = f"{self.client_id}:{self.client_secret}".encode()
        return "Basic " + base64.b64encode(raw).decode("ascii")

    def _send(self, method: str, url: str, **kwargs: object) -> httpx.Response:
        try:
            return self._http.request(method, url, **kwargs)
        except httpx.HTTPError:
            raise XUnavailable() from None

    def _json(self, response: httpx.Response) -> tuple[dict, Limits]:
        limits = read_limits(response.headers)
        if response.status_code >= 400:
            raise XHttp(response.status_code, limits)
        try:
            body = response.json()
        except ValueError:
            raise XHttp(502, limits) from None
        if not isinstance(body, dict):
            raise XHttp(502, limits)
        return body, limits

    def exchange(self, code: str, verifier: str) -> tuple[TokenBundle, Limits]:
        response = self._send(
            "POST",
            TOKEN_URL,
            headers={
                "Authorization": self._basic(),
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": self.redirect_uri,
                "code_verifier": verifier,
                "client_id": self.client_id,
            },
        )
        body, limits = self._json(response)
        return _bundle(body), limits

    def refresh(self, refresh_token: str) -> tuple[TokenBundle, Limits]:
        response = self._send(
            "POST",
            TOKEN_URL,
            headers={
                "Authorization": self._basic(),
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": self.client_id,
            },
        )
        body, limits = self._json(response)
        return _bundle(body, fallback_refresh=refresh_token), limits

    def revoke(self, token: str) -> None:
        response = self._send(
            "POST",
            REVOKE_URL,
            headers={
                "Authorization": self._basic(),
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={"token": token, "token_type_hint": "refresh_token", "client_id": self.client_id},
        )
        if response.status_code >= 400:
            raise XHttp(response.status_code, read_limits(response.headers))

    def me(self, access: str) -> tuple[XUser, Limits]:
        response = self._send(
            "GET",
            f"{API}/users/me",
            headers={"Authorization": f"Bearer {access}"},
            params={"user.fields": "username"},
        )
        body, limits = self._json(response)
        data = body.get("data")
        if not isinstance(data, dict):
            raise XHttp(502, limits)
        user_id = str(data.get("id") or "")
        username = str(data.get("username") or "")
        if not user_id.isdigit() or not username:
            raise XHttp(502, limits)
        return XUser(user_id, username[:15]), limits

    def bookmarks(self, access: str, user_id: str) -> tuple[dict, Limits]:
        response = self._send(
            "GET",
            f"{API}/users/{user_id}/bookmarks",
            headers={"Authorization": f"Bearer {access}"},
            params={
                "max_results": "10",
                "tweet.fields": "author_id,created_at,text",
                "expansions": "author_id",
                "user.fields": "username",
            },
        )
        return self._json(response)

    def search_recent(self, access: str, query: str, since_id: str | None) -> tuple[dict, Limits]:
        params = {
            "query": query,
            "max_results": "10",
            "tweet.fields": "author_id,created_at,text",
            "expansions": "author_id",
            "user.fields": "username",
        }
        if since_id:
            params["since_id"] = since_id
        response = self._send(
            "GET",
            f"{API}/tweets/search/recent",
            headers={"Authorization": f"Bearer {access}"},
            params=params,
        )
        return self._json(response)

    def post_tweet(self, access: str, text: str) -> tuple[str, Limits]:
        response = self._send(
            "POST",
            f"{API}/tweets",
            headers={"Authorization": f"Bearer {access}", "Content-Type": "application/json"},
            json={"text": text},
        )
        body, limits = self._json(response)
        data = body.get("data")
        if not isinstance(data, dict) or not str(data.get("id") or "").isdigit():
            raise XHttp(502, limits)
        return str(data["id"]), limits
