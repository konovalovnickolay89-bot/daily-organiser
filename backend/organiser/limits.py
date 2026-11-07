"""Per-process burst limits. They reset when the process restarts.

The daily assistant cap is separate. This only slows a tight loop against the
feed, the curator ingest, and the commute push. Nothing here is shared with
another process, and nothing is written down.
"""

import threading
import time
from collections import deque

from organiser.config import get_settings

_WINDOWS = {
    "feed": ("rate_feed_per_minute", 60.0),
    "ingest": ("rate_ingest_per_minute", 60.0),
    "commute": ("rate_commute_per_hour", 3600.0),
    "commute_disruption": ("rate_commute_disruption_per_hour", 3600.0),
}


class SlidingWindow:
    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def allow(self, name: str, now: float | None = None) -> bool:
        field, window = _WINDOWS[name]
        limit = int(getattr(get_settings(), field))
        moment = time.monotonic() if now is None else now
        with self._lock:
            hits = self._hits.setdefault(name, deque())
            while hits and moment - hits[0] >= window:
                hits.popleft()
            if limit <= 0 or len(hits) >= limit:
                return False
            hits.append(moment)
            return True

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


LIMITS = SlidingWindow()
