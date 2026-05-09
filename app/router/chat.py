from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, Request, Query

from app.core.deps import require_session
from app.core.connection_manager import manager
from app.db.mongodb import get_database
from app.schemas.message import ChatHistoryResponse
from app.services.chat_service import save_message, get_chat_history, verify_match_access
from app.services.notification_service import notify_new_message
from app.middleware.user_rate_limit import message_limiter

router = APIRouter(prefix="/chat", tags=["Chat"])


# ── WebSocket ─────────────────────────────────────────────────
# URL: ws://localhost:8000/chat/ws/{match_id}
# Auth: user_id lấy từ cookie session (không dùng query param nữa)

@router.websocket("/ws/{match_id}")
async def websocket_chat(websocket: WebSocket, match_id: str):
    # Lấy session từ cookie (Starlette SessionMiddleware populate request.session)
    session = websocket.session  # type: ignore[attr-defined]
    user_id  = session.get("user_id", "")
    username = session.get("username", "")

    if not user_id:
        await websocket.close(code=4001, reason="Not authenticated")
        return

    db = get_database()

    # Kiểm tra quyền
    has_access = await verify_match_access(db, match_id, user_id)
    if not has_access:
        await websocket.close(code=4003, reason="Access denied")
        return

    # Kết nối (giới hạn 2 người/phòng)
    connected = await manager.connect(match_id, websocket, user_id)
    if not connected:
        return  # close đã được gọi bên trong connect()

    # Gửi lịch sử 50 tin nhắn gần nhất
    history = await get_chat_history(db, match_id, limit=50)
    await websocket.send_json({
        "type": "history",
        "messages": [m.model_dump(mode="json") for m in history.messages],
        "has_more": history.has_more,
        "next_cursor": history.next_cursor,
    })

    # Thông báo vào phòng (chỉ gửi cho người còn lại)
    await manager.broadcast_to_room(match_id, {
        "type": "system",
        "content": f"{username} đã vào phòng chat.",
        "user_online": True,
    }, exclude=websocket)

    try:
        while True:
            data = await websocket.receive_json()
            content = data.get("content", "").strip()

            if not content:
                continue

            if len(content) > 500:
                await websocket.send_json({
                    "type": "error",
                    "content": "Tin nhắn quá dài (tối đa 500 ký tự)",
                })
                continue

            # Rate limit tin nhắn
            try:
                message_limiter.check(user_id, "messages")
            except Exception as e:
                await websocket.send_json({"type": "error", "content": str(e)})
                continue

            message = await save_message(db, match_id, user_id, username, content)
            payload = {
                "type": "message",
                "message": message.model_dump(mode="json"),
            }

            # Gửi cho tất cả trong phòng (kể cả người gửi để confirm)
            await manager.broadcast_to_room(match_id, payload)

            # Thông báo push cho người kia nếu họ không ở trong phòng
            if manager.get_room_size(match_id) < 2:
                from bson import ObjectId
                match_doc = await db.matches.find_one({"_id": ObjectId(match_id)})
                if match_doc:
                    other_id = (
                        str(match_doc["user2_id"])
                        if str(match_doc["user1_id"]) == user_id
                        else str(match_doc["user1_id"])
                    )
                    await notify_new_message(other_id, message.model_dump(mode="json"), username)

    except WebSocketDisconnect:
        manager.disconnect(match_id, websocket, user_id)
        await manager.broadcast_to_room(match_id, {
            "type": "system",
            "content": f"{username} đã rời phòng chat.",
            "user_online": False,
        })


# ── REST: lịch sử chat với cursor pagination ──────────────────

@router.get("/{match_id}/history", response_model=ChatHistoryResponse)
async def chat_history(
    match_id: str,
    request: Request,
    limit: int = Query(default=50, ge=1, le=100),
    before_id: str | None = Query(default=None, description="Cursor: lấy tin nhắn cũ hơn ID này"),
):
    user_id = require_session(request)
    db = get_database()

    has_access = await verify_match_access(db, match_id, user_id)
    if not has_access:
        raise HTTPException(status_code=403, detail="Access denied")

    try:
        return await get_chat_history(db, match_id, limit=limit, before_id=before_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ── WebSocket: notification channel riêng ────────────────────
# URL: ws://localhost:8000/chat/notifications
# Dùng để nhận push notification khi không ở trong phòng chat

@router.websocket("/notifications")
async def notification_channel(websocket: WebSocket):
    session = websocket.session  # type: ignore[attr-defined]
    user_id = session.get("user_id", "")

    if not user_id:
        await websocket.close(code=4001, reason="Not authenticated")
        return

    await manager.register_notification(user_id, websocket)
    manager.mark_online(user_id)

    try:
        while True:
            # Giữ kết nối sống — client gửi ping định kỳ
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
                manager.mark_online(user_id)
    except WebSocketDisconnect:
        manager.unregister_notification(user_id)
        manager.mark_offline(user_id)
