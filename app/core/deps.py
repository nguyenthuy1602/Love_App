"""
Shared dependencies dùng chung cho tất cả router.
"""
from fastapi import HTTPException, Request


def require_session(request: Request) -> str:
    """Trả về user_id nếu đã login, raise 401 nếu chưa."""
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user_id


def require_session_full(request: Request) -> tuple[str, str]:
    """Trả về (user_id, username) nếu đã login, raise 401 nếu chưa."""
    user_id = request.session.get("user_id")
    username = request.session.get("username", "")
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user_id, username
