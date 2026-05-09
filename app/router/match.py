from fastapi import APIRouter, HTTPException, Request
from typing import Optional

from app.core.deps import require_session
from app.db.mongodb import get_database
from app.schemas.match import MatchResponse
from app.services.matching_service import (
    suggest_by_sentiment, suggest_random,
    accept_match, skip_match, get_my_matches,
)
from app.services.moderation_service import unmatch
from app.services.notification_service import notify_new_match

router = APIRouter(prefix="/match", tags=["Matching"])


@router.get("/suggest", response_model=Optional[MatchResponse])
async def suggest_sentiment_match(request: Request):
    user_id = require_session(request)
    db = get_database()
    try:
        return await suggest_by_sentiment(db, user_id)
    except ValueError as e:
        if str(e) == "No available users to match":
            return None
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/random", response_model=Optional[MatchResponse])
async def random_match(request: Request):
    user_id = require_session(request)
    db = get_database()
    try:
        return await suggest_random(db, user_id)
    except ValueError as e:
        if str(e) == "No available users to match":
            return None
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{match_id}/accept", response_model=MatchResponse)
async def accept(match_id: str, request: Request):
    user_id = require_session(request)
    db = get_database()
    try:
        match = await accept_match(db, match_id, user_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

    # Thông báo cho người kia biết đã được accept
    await notify_new_match(
        match.user2_id,
        {"match_id": match.id, "from_username": match.user1_username},
    )
    return match


@router.post("/{match_id}/skip", status_code=204)
async def skip(match_id: str, request: Request):
    user_id = require_session(request)
    db = get_database()
    try:
        await skip_match(db, match_id, user_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.post("/{match_id}/unmatch", status_code=204)
async def unmatch_match(match_id: str, request: Request):
    user_id = require_session(request)
    db = get_database()
    try:
        await unmatch(db, match_id, user_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.get("/me", response_model=list[MatchResponse])
async def my_matches(request: Request):
    user_id = require_session(request)
    db = get_database()
    return await get_my_matches(db, user_id)
