from fastapi import APIRouter, HTTPException, Request

from app.core.deps import require_session
from app.db.mongodb import get_database
from app.schemas.moderation import BlockResponse, ReportRequest, ReportResponse
from app.services.moderation_service import (
    block_user, unblock_user, get_blocked_users, report_target
)

router = APIRouter(prefix="/users", tags=["Moderation"])


@router.post("/{user_id}/block", response_model=BlockResponse)
async def block(user_id: str, request: Request):
    blocker_id = require_session(request)
    db = get_database()
    try:
        return await block_user(db, blocker_id, user_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{user_id}/block", status_code=204)
async def unblock(user_id: str, request: Request):
    blocker_id = require_session(request)
    db = get_database()
    try:
        await unblock_user(db, blocker_id, user_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/me/blocked", response_model=list[dict])
async def my_blocked_list(request: Request):
    user_id = require_session(request)
    db = get_database()
    return await get_blocked_users(db, user_id)


@router.post("/report", response_model=ReportResponse, status_code=201)
async def report(body: ReportRequest, request: Request):
    reporter_id = require_session(request)
    db = get_database()
    try:
        return await report_target(db, reporter_id, body)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
