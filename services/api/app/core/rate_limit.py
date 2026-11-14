from __future__ import annotations

import math
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from threading import Lock


@dataclass(frozen=True)
class RateLimitDecision:
    allowed: bool
    remaining: int
    retry_after_seconds: int


class SlidingWindowRateLimiter:
    """Thread-safe in-memory sliding-window rate limiter with bounded bucket growth."""

    def __init__(self, max_buckets: int = 20_000) -> None:
        self._lock = Lock()
        self._buckets: dict[str, deque[float]] = defaultdict(deque)
        self._max_buckets = max_buckets

    def check(self, key: str, limit: int, window_seconds: int) -> RateLimitDecision:
        if limit <= 0:
            return RateLimitDecision(allowed=True, remaining=0, retry_after_seconds=0)
        now = time.monotonic()
        cutoff = now - float(window_seconds)
        with self._lock:
            if len(self._buckets) > self._max_buckets and key not in self._buckets:
                # Evict empty or oldest buckets defensively against memory exhaustion
                stale_keys = [
                    k for k, q in list(self._buckets.items()) if not q or q[-1] < cutoff
                ]
                for k in stale_keys:
                    del self._buckets[k]
                if len(self._buckets) > self._max_buckets:
                    self._buckets.clear()

            bucket = self._buckets[key]
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()

            if len(bucket) >= limit:
                retry_after = max(1, math.ceil(bucket[0] + float(window_seconds) - now))
                return RateLimitDecision(
                    allowed=False,
                    remaining=0,
                    retry_after_seconds=retry_after,
                )

            bucket.append(now)
            return RateLimitDecision(
                allowed=True,
                remaining=max(0, limit - len(bucket)),
                retry_after_seconds=0,
            )

    def clear(self) -> None:
        with self._lock:
            self._buckets.clear()


class RuntimeMetricsCollector:
    """Lightweight thread-safe API performance & error telemetry tracker."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._requests_total = 0
        self._errors_5xx = 0
        self._errors_4xx = 0
        self._latency_ms_sum = 0.0
        self._latency_ms_max = 0.0

    def record(self, status_code: int, latency_ms: float) -> None:
        with self._lock:
            self._requests_total += 1
            self._latency_ms_sum += latency_ms
            if latency_ms > self._latency_ms_max:
                self._latency_ms_max = latency_ms
            if status_code >= 500:
                self._errors_5xx += 1
            elif status_code >= 400:
                self._errors_4xx += 1

    def snapshot(self) -> dict[str, float | int]:
        with self._lock:
            avg_ms = (
                round(self._latency_ms_sum / self._requests_total, 2)
                if self._requests_total > 0
                else 0.0
            )
            return {
                "requests_total": self._requests_total,
                "errors_4xx": self._errors_4xx,
                "errors_5xx": self._errors_5xx,
                "avg_latency_ms": avg_ms,
                "max_latency_ms": round(self._latency_ms_max, 2),
            }

    def reset(self) -> None:
        with self._lock:
            self._requests_total = 0
            self._errors_4xx = 0
            self._errors_5xx = 0
            self._latency_ms_sum = 0.0
            self._latency_ms_max = 0.0


rate_limiter = SlidingWindowRateLimiter()
metrics_collector = RuntimeMetricsCollector()
