from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class MessageResponse(BaseModel):
    id: str
    match_id: str
    sender_id: str
    sender_username: str
    content: str
    created_at: datetime


class ChatHistoryResponse(BaseModel):
    messages: list[MessageResponse]
    match_id: str
    has_more: bool = False
    next_cursor: Optional[str] = None   # ObjectId của tin nhắn cũ nhất → dùng cho pagination
