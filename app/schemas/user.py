from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


# ── Request schemas ──────────────────────────────────────────

class UserRegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=30)
    password: str = Field(..., min_length=6)
    bio: Optional[str] = Field(default=None, max_length=200)


class UserLoginRequest(BaseModel):
    username: str
    password: str


class UserUpdateRequest(BaseModel):
    bio: Optional[str] = Field(default=None, max_length=200)


# ── Response schemas ─────────────────────────────────────────

class UserResponse(BaseModel):
    id: str
    username: str
    bio: Optional[str] = None
    avatar_url: Optional[str] = None
    sentiment_profile: Optional[str] = None   # positive / neutral / negative
    is_online: bool = False
    created_at: datetime


class LoginResponse(BaseModel):
    message: str
    user: UserResponse
