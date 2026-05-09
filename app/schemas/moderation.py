from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum
from typing import Optional


class ReportReason(str, Enum):
    SPAM        = "spam"
    HARASSMENT  = "harassment"
    HATE_SPEECH = "hate_speech"
    FAKE        = "fake_profile"
    OTHER       = "other"


class ReportRequest(BaseModel):
    target_id: str
    target_type: str = "user"              # "user" | "post"
    reason: ReportReason
    description: Optional[str] = Field(default=None, max_length=300)


class BlockResponse(BaseModel):
    blocker_id: str
    blocked_id: str
    blocked_username: str
    created_at: datetime


class ReportResponse(BaseModel):
    id: str
    reporter_id: str
    target_id: str
    target_type: str
    reason: str
    status: str = "pending"
    created_at: datetime
