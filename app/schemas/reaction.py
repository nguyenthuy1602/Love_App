from pydantic import BaseModel
from datetime import datetime
from enum import Enum


class ReactionType(str, Enum):
    HEART = "heart"
    SAD   = "sad"
    WOW   = "wow"
    HAHA  = "haha"
    FIRE  = "fire"


class ReactionRequest(BaseModel):
    reaction_type: ReactionType


class ReactionResponse(BaseModel):
    post_id: str
    user_id: str
    reaction_type: ReactionType
    created_at: datetime


class ReactionCountResponse(BaseModel):
    post_id: str
    heart: int = 0
    sad: int = 0
    wow: int = 0
    haha: int = 0
    fire: int = 0
    my_reaction: str | None = None
