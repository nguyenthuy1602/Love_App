"""
User-level rate limiter cho bài đăng và tin nhắn.
Tách riêng khỏi IP-based middleware vì cần gắn với user_id.
"""

import time
from collections import defaultdict, deque
from fastapi import HTTPException

from app.core.config import settings


class UserRateLimiter:
    def __init__(self, limit: int, window: int):
        self._limit = limit
        self._window = window
        self._windows: dict[str, deque] = defaultdict(deque)

    def check(self, user_id: str, action: str = "action"):
        now = time.time()
        window = self._windows[user_id]
        while window and window[0] < now - self._window:
            window.popleft()
        if len(window) >= self._limit:
            retry = int(self._window - (now - window[0]))
            raise HTTPException(
                status_code=429,
                detail=f"Too many {action}. Please wait {retry}s.",
                headers={"Retry-After": str(retry)},
            )
        window.append(now)


# Singletons
post_limiter    = UserRateLimiter(settings.rate_limit_post_per_hour,    3600)
message_limiter = UserRateLimiter(settings.rate_limit_message_per_minute, 60)
