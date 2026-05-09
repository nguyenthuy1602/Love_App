from fastapi import APIRouter, HTTPException, Request, Query
from bson import ObjectId

from app.core.deps import require_session, require_session_full
from app.db.mongodb import get_database
from app.schemas.comment import CommentCreateRequest, CommentResponse, CommentListResponse
from app.services.comment_service import add_comment, get_comments, delete_comment
from app.services.notification_service import notify_new_comment

router = APIRouter(prefix="/posts", tags=["Comments"])


@router.post("/{post_id}/comments", response_model=CommentResponse, status_code=201)
async def create_comment(post_id: str, body: CommentCreateRequest, request: Request):
    user_id, username = require_session_full(request)
    db = get_database()

    # Lấy avatar
    user_doc = await db.users.find_one({"username": username}, {"avatar_url": 1})
    avatar_url = user_doc.get("avatar_url") if user_doc else None

    try:
        comment = await add_comment(db, post_id, user_id, username, body.content, avatar_url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Thông báo cho chủ bài
    post = await db.posts.find_one(
        {"_id": ObjectId(post_id)}, {"user_id": 1}
    )
    if post and str(post["user_id"]) != user_id:
        await notify_new_comment(str(post["user_id"]), post_id, username, body.content)

    return comment


@router.get("/{post_id}/comments", response_model=CommentListResponse)
async def list_comments(
    post_id: str,
    request: Request,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=50),
):
    require_session(request)
    db = get_database()
    try:
        return await get_comments(db, post_id, page=page, page_size=page_size)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/comments/{comment_id}", status_code=204)
async def delete_my_comment(comment_id: str, request: Request):
    user_id = require_session(request)
    db = get_database()
    try:
        await delete_comment(db, comment_id, user_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
