"""One JSON call. Callers must not log the URL: it can carry a location or a token."""

from typing import Any

import httpx


def request_json_any(
    method: str,
    url: str,
    *,
    params: dict | None = None,
    data: dict | None = None,
    headers: dict | None = None,
    timeout: float = 8.0,
) -> Any:
    with httpx.Client(timeout=timeout) as client:
        response = client.request(method, url, params=params, data=data, headers=headers)
        response.raise_for_status()
        body = response.json()
    if not isinstance(body, (dict, list)):
        raise ValueError("The response was not JSON.")
    return body


def request_json(
    method: str,
    url: str,
    *,
    params: dict | None = None,
    data: dict | None = None,
    headers: dict | None = None,
    timeout: float = 8.0,
) -> dict:
    body = request_json_any(method, url, params=params, data=data, headers=headers, timeout=timeout)
    if not isinstance(body, dict):
        raise ValueError("The response was not a JSON object.")
    return body
