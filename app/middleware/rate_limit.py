"""
Rate Limit Middleware
Giới hạn số request/phút theo IP để chống spam và DDoS cơ bản.
Dùng sliding window in-memory (đủ dùng cho single-process).
Production: thay bằng Redis-backed rate limiter.
"""

import time
from collections import defaultdict, deque

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.core.config import settings


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        # { ip: deque of timestamps }
        self._windows: dict[str, deque] = defaultdict(deque)
        self._limit = settings.rate_limit_per_minute
        self._window = 60  # seconds

    def _get_ip(self, request: Request) -> str:
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    async def dispatch(self, request: Request, call_next) -> Response:
        # Bỏ qua health check và WebSocket
        path = request.url.path
        if path in ("/health",) or request.headers.get("upgrade", "").lower() == "websocket":
            return await call_next(request)

        ip = self._get_ip(request)
        now = time.time()
        window = self._windows[ip]

        # Xóa timestamps cũ hơn 1 phút
        while window and window[0] < now - self._window:
            window.popleft()

        if len(window) >= self._limit:
            return JSONResponse(
                status_code=429,
                content={
                    "detail": f"Too many requests. Limit: {self._limit}/minute.",
                    "retry_after": int(self._window - (now - window[0])),
                },
                headers={"Retry-After": str(int(self._window - (now - window[0])))},
            )

        window.append(now)
        return await call_next(request)
