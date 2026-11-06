"""Whether Smart Add may be shown. GET routes do not call Mistral to find out.

A failed call hides the box for a short while. The next successful call, or the
end of that wait, shows it again. The wait lives in this process only.
"""

import time

COOLDOWN_SECONDS = 90.0

_until = 0.0


def mark_down(seconds: float = COOLDOWN_SECONDS) -> None:
    global _until
    _until = time.monotonic() + seconds


def mark_up() -> None:
    global _until
    _until = 0.0


def is_reachable(configured: bool, now: float | None = None) -> bool:
    if not configured:
        return False
    moment = time.monotonic() if now is None else now
    return moment >= _until


def reset() -> None:
    global _until
    _until = 0.0
