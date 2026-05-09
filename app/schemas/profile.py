from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from app.schemas.post import PostResponse


class ProfileResponse(BaseModel):
    id: str
    username: str
    bio: Optional[str] = None
    avatar_url: Optional[str] = None
    sentiment_profile: Optional[str] = None
    is_online: bool = False
    created_at: datetime
    posts: list[PostResponse] = []


class ProfileUpdateRequest(BaseModel):
    bio: Optional[str] = Field(default=None, max_length=200)
    avatar_url: Optional[str] = Field(default=None, max_length=500)
