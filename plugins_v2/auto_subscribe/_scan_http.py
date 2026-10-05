"""Per-scan TMDB start pacing through the platform HTTP facade only."""

from __future__ import annotations

import asyncio
from datetime import timezone
from email.utils import parsedate_to_datetime
import math
from time import monotonic, time
from urllib.parse import urlsplit


_TMDB_HOST = "api.themoviedb.org"
_MAX_WAIT_SLICE = 1.0


def _retry_after_delay(response, fallback):
    """Accept seconds or an HTTP date without exposing response contents."""
    raw = ""
    try:
        raw = response.headers.get("Retry-After")
        if raw is None:
            raw = response.headers.get("retry-after")
        raw = str(raw).strip() if raw is not None else ""
    except (AttributeError, TypeError, ValueError, OverflowError):
        pass
    try:
        delay = float(raw)
        if math.isfinite(delay) and delay >= 0:
            return delay
    except (TypeError, ValueError, OverflowError):
        pass
    if raw:
        try:
            when = parsedate_to_datetime(raw)
            if when.tzinfo is None:
                when = when.replace(tzinfo=timezone.utc)
            delay = when.timestamp() - time()
            if math.isfinite(delay):
                return max(0.0, delay)
        except (AttributeError, TypeError, ValueError, OverflowError):
            pass
    return fallback


class ScanHttp:
    """Pace TMDB GET starts fairly; leave Emby requests unchanged.

    A scan owns one instance and its shared cooldown. The caller still owns
    concurrency, request/scan deadlines, and cancellation. This helper never
    constructs an HTTP client, retries a request, or changes HTTP responses.
    """

    def __init__(self, http, *, starts_per_second=10.0, default_cooldown=3.0):
        if (isinstance(starts_per_second, bool)
                or not isinstance(starts_per_second, (int, float))
                or not math.isfinite(starts_per_second) or not 0 < starts_per_second <= 10
                or not math.isfinite(1.0 / starts_per_second)):
            raise ValueError("请求启动速率必须是大于 0 且不超过 10 的有限值")
        if (isinstance(default_cooldown, bool)
                or not isinstance(default_cooldown, (int, float))
                or not math.isfinite(default_cooldown) or default_cooldown < 0):
            raise ValueError("限流等待时间必须是有限非负数")
        self._http = http
        self._interval = 1.0 / starts_per_second
        self._default_cooldown = default_cooldown
        self._gate = asyncio.Lock()
        self._next_start = 0.0
        self._cooldown_until = 0.0

    async def _wait_start(self):
        # asyncio.Lock gives FIFO acquisition. Only its current owner waits;
        # queued callers never reserve timestamps that can all expire while
        # the SDK synchronously initializes a Windows TLS client.
        async with self._gate:
            while True:
                # Yield even when overdue: KV completions/cancellation must
                # get a scheduling turn before another synchronous TLS init.
                await asyncio.sleep(0)
                now = monotonic()
                remaining = max(self._next_start, self._cooldown_until) - now
                if remaining <= 0:
                    self._next_start = now + self._interval
                    return
                # Long valid server cooldowns are not shortened. Small wait
                # slices remain cancellable and recheck shared extensions.
                await asyncio.sleep(min(remaining, _MAX_WAIT_SLICE))

    async def get(self, url, **kwargs):
        try:
            is_tmdb = urlsplit(str(url)).hostname == _TMDB_HOST
        except (TypeError, ValueError):
            is_tmdb = False
        if not is_tmdb:
            return await self._http.get(url, **kwargs)
        await self._wait_start()
        response = await self._http.get(url, **kwargs)
        if getattr(response, "status_code", None) == 429:
            delay = _retry_after_delay(response, self._default_cooldown)
            self._cooldown_until = max(self._cooldown_until, monotonic() + delay)
        return response
