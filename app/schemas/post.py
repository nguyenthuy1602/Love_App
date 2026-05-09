from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional
from datetime import datetime
from enum import Enum


class MediaType(str, Enum):
    IMAGE = "image"
    VIDEO = "video"


# ── Request schemas ──────────────────────────────────────────

class PostCreateRequest(BaseModel):
    content: str = Field(default="", max_length=1000)
    media_urls: list[str] = Field(default_factory=list, max_length=4)
    media_type: Optional[MediaType] = None

    @field_validator("content", mode="before")
    @classmethod
    def normalize_content(cls, value):
        if value is None:
            return ""
        return str(value).strip()

    @field_validator("media_type", mode="before")
    @classmethod
    def normalize_media_type(cls, value):
        if value is None:
            return None
        v = str(value).strip().lower()
        if v == "":
            return None
        if v in ("image", "video"):
            return v
        raise ValueError("media_type must be 'image' or 'video'")

    @model_validator(mode="after")
    def validate_content_or_media(self):
        if not self.content and not self.media_urls:
            raise ValueError("content or media_urls is required")
        if self.media_urls and self.media_type is None:
            raise ValueError("media_type is required when media_urls is provided")
        if not self.media_urls and self.media_type is not None:
            raise ValueError("media_type must be null when media_urls is empty")
        return self


# ── Response schemas ─────────────────────────────────────────

class ReactionSummary(BaseModel):
    """Số lượng từng loại reaction trên bài viết."""
    heart: int = 0
    sad: int = 0
    wow: int = 0
    haha: int = 0
    fire: int = 0
    my_reaction: Optional[str] = None   # reaction của user hiện tại nếu có


class PostResponse(BaseModel):
    id: str
    user_id: str
    username: str
    avatar_url: Optional[str] = None
    content: str
    media_urls: list[str] = []
    media_type: Optional[MediaType] = None
    sentiment_score: Optional[str] = None
    sentiment_confidence: Optional[float] = None   # 0.0 – 1.0
    reactions: ReactionSummary = ReactionSummary()
    comment_count: int = 0
    created_at: datetime


class FeedResponse(BaseModel):
    posts: list[PostResponse]
    total: int
    page: int
    page_size: int
