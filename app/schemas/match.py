from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from enum import Enum


class MatchStatus(str, Enum):
    PENDING  = "pending"
    ACCEPTED = "accepted"
    SKIPPED  = "skipped"
    UNMATCHED = "unmatched"


class MatchResponse(BaseModel):
    id: str
    user1_id: str
    user2_id: str
    user1_username: str
    user2_username: str
    user2_bio: Optional[str] = None
    user2_avatar_url: Optional[str] = None
    user2_sentiment: Optional[str] = None
    partner_is_online: bool = False
    status: MatchStatus
    created_at: datetime
