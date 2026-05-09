from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional


class CommentCreateRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=500)


class CommentResponse(BaseModel):
    id: str
    post_id: str
    user_id: str
    username: str
    avatar_url: Optional[str] = None
    content: str
    created_at: datetime


class CommentListResponse(BaseModel):
    comments: list[CommentResponse]
    total: int
    post_id: str
