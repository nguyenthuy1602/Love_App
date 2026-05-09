from fastapi import APIRouter, HTTPException, Request

from app.core.deps import require_session
from app.db.mongodb import get_database
from app.schemas.profile import ProfileResponse, ProfileUpdateRequest
from app.services.profile_service import get_profile, update_profile

router = APIRouter(prefix="/profile", tags=["Profile"])


@router.get("/me", response_model=ProfileResponse)
async def my_profile(request: Request):
    user_id = require_session(request)
    db = get_database()
    try:
        return await get_profile(db, user_id, viewer_user_id=user_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{user_id}", response_model=ProfileResponse)
async def view_profile(user_id: str, request: Request):
    viewer_id = require_session(request)
    db = get_database()
    try:
        return await get_profile(db, user_id, viewer_user_id=viewer_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.patch("/me", response_model=ProfileResponse)
async def update_my_profile(body: ProfileUpdateRequest, request: Request):
    user_id = require_session(request)
    db = get_database()
    try:
        return await update_profile(db, user_id, body)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
