"""Rate limits on sign-in, scoring and uploads.

A moving window per (scope, key), kept in the memory of each API process: with N workers a
client can get up to N times a limit. That is enough to slow password guessing and runaway
scripts; a shared store (Redis) would make the limits exact.
"""

import math
import time

from limits import parse
from limits.storage import MemoryStorage
from limits.strategies import MovingWindowRateLimiter

from app.core.config import Settings
from app.core.errors import TooManyRequests
from app.core.metrics import RATE_LIMITED


class RateLimiter:
    def __init__(self, settings: Settings):
        self._storage = MemoryStorage()
        self._limiter = MovingWindowRateLimiter(self._storage)
        configured = {
            "login": settings.rate_limit_login,
            "login_account": settings.rate_limit_login_account,
            "scoring": settings.rate_limit_scoring,
            "upload": settings.rate_limit_upload,
        }
        self._limits = {scope: parse(value) for scope, value in configured.items() if value}

    def hit(self, scope: str, key: str, cost: int = 1) -> None:
        """Count `cost` against the scope's limit for `key`; raise TooManyRequests when over."""
        item = self._limits.get(scope)
        if item is None:
            return
        # A cost above the limit could never pass; let it use up the whole window instead.
        if self._limiter.hit(item, scope, key, cost=min(cost, item.amount)):
            return
        reset_time, _ = self._limiter.get_window_stats(item, scope, key)
        RATE_LIMITED.labels(scope).inc()
        raise TooManyRequests(max(1, math.ceil(reset_time - time.time())))

    def reset(self) -> None:
        self._storage.reset()
