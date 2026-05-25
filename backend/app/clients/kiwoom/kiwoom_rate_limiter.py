from __future__ import annotations

import time


class KiwoomRateLimiter:
    def __init__(self, rate_limit_per_second: float) -> None:
        self._rate_limit_per_second = max(float(rate_limit_per_second or 0), 0.0)
        self._last_called_at = 0.0

    def throttle(self) -> None:
        if self._rate_limit_per_second <= 0:
            return
        min_interval = 1.0 / self._rate_limit_per_second
        now = time.monotonic()
        remain = min_interval - (now - self._last_called_at)
        if remain > 0:
            time.sleep(remain)
        self._last_called_at = time.monotonic()

