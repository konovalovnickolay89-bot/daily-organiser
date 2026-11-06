"""Process metrics for the house. Counts and timings only.

Nothing here stores a request body, a transcript, a postcode, or a secret.
The counters reset when the process restarts.
"""

import threading
import time
from collections import defaultdict
from datetime import datetime, timedelta

from organiser import clock

FAILURE_WINDOW = timedelta(minutes=15)
POLL_STALE = timedelta(hours=2)

CONTENT_TYPE = "text/plain; version=0.0.4; charset=utf-8"


def _label(value: str) -> str:
    return value.replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')


def _seconds(value: float) -> str:
    return f"{value:.6f}"


class Metrics:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.reset()

    def reset(self) -> None:
        with self._lock:
            self.started_at = clock.current_time()
            self.requests: dict[tuple[str, str, str], int] = defaultdict(int)
            self.latency_sum: dict[tuple[str, str], float] = defaultdict(float)
            self.latency_count: dict[tuple[str, str], int] = defaultdict(int)
            self.mistral_ok = 0
            self.mistral_error = 0
            self.mistral_seconds = 0.0
            self.mistral_calls = 0
            self.last_mistral_success: datetime | None = None
            self._failures: list[datetime] = []
            self.last_poll: datetime | None = None
            self.last_db_error: datetime | None = None
            self.proposal_queue = 0

    def record_request(self, method: str, route: str, status: int, seconds: float) -> None:
        key = (method.upper(), route, str(status))
        latency = (method.upper(), route)
        with self._lock:
            self.requests[key] += 1
            self.latency_sum[latency] += max(0.0, seconds)
            self.latency_count[latency] += 1

    def record_mistral(self, *, ok: bool, seconds: float, at: datetime) -> None:
        with self._lock:
            self.mistral_calls += 1
            self.mistral_seconds += max(0.0, seconds)
            if ok:
                self.mistral_ok += 1
                self.last_mistral_success = at
            else:
                self.mistral_error += 1
                self._failures.append(at)

    def record_poll(self, at: datetime) -> None:
        with self._lock:
            self.last_poll = at

    def record_db_error(self, at: datetime) -> None:
        with self._lock:
            self.last_db_error = at

    def set_proposal_queue(self, size: int) -> None:
        with self._lock:
            self.proposal_queue = size

    def failures_in_window(self, now: datetime) -> list[datetime]:
        cutoff = now - FAILURE_WINDOW
        with self._lock:
            self._failures = [moment for moment in self._failures if moment >= cutoff]
            return list(self._failures)

    def health(self, now: datetime) -> str:
        with self._lock:
            error = self.last_db_error
        if error is not None and now - error <= FAILURE_WINDOW:
            return "degraded"
        return "ok"

    def render(self, now: datetime) -> str:
        with self._lock:
            requests = sorted(self.requests.items())
            latency = sorted(self.latency_sum.items())
            latency_count = dict(self.latency_count)
            mistral_ok = self.mistral_ok
            mistral_error = self.mistral_error
            mistral_seconds = self.mistral_seconds
            mistral_calls = self.mistral_calls
            last_poll = self.last_poll
            queue = self.proposal_queue
        if last_poll is None:
            poll_age = -1.0
        else:
            poll_age = max(0.0, (now - last_poll).total_seconds())
        lines = [
            "# HELP organiser_http_requests_total HTTP requests handled by this process.",
            "# TYPE organiser_http_requests_total counter",
        ]
        for (method, route, status), count in requests:
            lines.append(
                f'organiser_http_requests_total{{method="{_label(method)}",route="{_label(route)}",status="{_label(status)}"}} {count}'
            )
        lines += [
            "# HELP organiser_http_request_duration_seconds HTTP request latency by route.",
            "# TYPE organiser_http_request_duration_seconds summary",
        ]
        for (method, route), total in latency:
            labels = f'method="{_label(method)}",route="{_label(route)}"'
            lines.append(f"organiser_http_request_duration_seconds_sum{{{labels}}} {_seconds(total)}")
            lines.append(
                f"organiser_http_request_duration_seconds_count{{{labels}}} {latency_count[(method, route)]}"
            )
        lines += [
            "# HELP organiser_mistral_calls_total Mistral calls by result.",
            "# TYPE organiser_mistral_calls_total counter",
            f'organiser_mistral_calls_total{{result="ok"}} {mistral_ok}',
            f'organiser_mistral_calls_total{{result="error"}} {mistral_error}',
            "# HELP organiser_mistral_duration_seconds Mistral call latency.",
            "# TYPE organiser_mistral_duration_seconds summary",
            f"organiser_mistral_duration_seconds_sum {_seconds(mistral_seconds)}",
            f"organiser_mistral_duration_seconds_count {mistral_calls}",
            "# HELP organiser_activity_poll_age_seconds Seconds since GET /agent/activity. -1 before the first poll.",
            "# TYPE organiser_activity_poll_age_seconds gauge",
            f"organiser_activity_poll_age_seconds {_seconds(poll_age)}",
            "# HELP organiser_proposal_queue Pending proposals waiting for Apply. -1 when the count could not be read.",
            "# TYPE organiser_proposal_queue gauge",
            f"organiser_proposal_queue {queue}",
            "",
        ]
        return "\n".join(lines)


METRICS = Metrics()


def observe_mistral(call):
    """Time one Mistral call. The exception still propagates. The audio and the text do not."""
    started = time.perf_counter()
    try:
        result = call()
    except Exception:
        METRICS.record_mistral(ok=False, seconds=time.perf_counter() - started, at=clock.current_time())
        raise
    METRICS.record_mistral(ok=True, seconds=time.perf_counter() - started, at=clock.current_time())
    return result
