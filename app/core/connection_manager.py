"""
Connection Manager — WebSocket
Quản lý kết nối WebSocket theo phòng chat (match_id).
Giới hạn 2 người/phòng. Theo dõi trạng thái online/offline.
"""

from fastapi import WebSocket
from collections import defaultdict
from datetime import datetime, timezone


class ConnectionManager:
    def __init__(self):
        # { match_id: [websocket, ...] }
        self.rooms: dict[str, list[WebSocket]] = defaultdict(list)

        # { user_id: datetime } — last seen
        self.online_users: dict[str, datetime] = {}

    # ── Room management ───────────────────────────────────────

    async def connect(self, match_id: str, websocket: WebSocket, user_id: str) -> bool:
        """
        Kết nối vào phòng. Trả về False nếu phòng đã đủ 2 người.
        """
        if len(self.rooms[match_id]) >= 2:
            await websocket.close(code=4004, reason="Room is full")
            return False

        await websocket.accept()
        self.rooms[match_id].append(websocket)
        self.online_users[user_id] = datetime.now(timezone.utc)
        return True

    def disconnect(self, match_id: str, websocket: WebSocket, user_id: str):
        room = self.rooms.get(match_id, [])
        if websocket in room:
            room.remove(websocket)
        if not room:
            self.rooms.pop(match_id, None)
        self.online_users.pop(user_id, None)

    async def broadcast_to_room(
        self,
        match_id: str,
        message: dict,
        exclude: WebSocket | None = None,
    ):
        """Gửi tin nhắn đến tất cả (hoặc trừ người gửi) trong phòng."""
        for ws in list(self.rooms.get(match_id, [])):
            if ws is exclude:
                continue
            try:
                await ws.send_json(message)
            except Exception:
                pass

    def get_room_size(self, match_id: str) -> int:
        return len(self.rooms.get(match_id, []))

    # ── Online presence ───────────────────────────────────────

    def mark_online(self, user_id: str):
        self.online_users[user_id] = datetime.now(timezone.utc)

    def mark_offline(self, user_id: str):
        self.online_users.pop(user_id, None)

    def is_online(self, user_id: str) -> bool:
        return user_id in self.online_users

    def get_last_seen(self, user_id: str) -> datetime | None:
        return self.online_users.get(user_id)

    # ── Global broadcast (notifications) ─────────────────────

    # { user_id: websocket } — kết nối notification riêng biệt
    _notification_sockets: dict[str, WebSocket] = {}

    async def register_notification(self, user_id: str, websocket: WebSocket):
        await websocket.accept()
        self._notification_sockets[user_id] = websocket

    def unregister_notification(self, user_id: str):
        self._notification_sockets.pop(user_id, None)

    async def send_notification(self, user_id: str, payload: dict):
        ws = self._notification_sockets.get(user_id)
        if ws:
            try:
                await ws.send_json(payload)
            except Exception:
                self.unregister_notification(user_id)


# Singleton
manager = ConnectionManager()
