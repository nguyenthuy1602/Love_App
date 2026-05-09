from fastapi import APIRouter, HTTPException, Request
from bson import ObjectId

from app.core.deps import require_session
from app.db.mongodb import get_database
from app.schemas.reaction import ReactionRequest, ReactionCountResponse
from app.services.reaction_service import react_to_post, get_reaction_counts
from app.services.notification_service import notify_new_reaction

router = APIRouter(prefix="/posts", tags=["Reactions"])


@router.post("/{post_id}/react", response_model=ReactionCountResponse)
async def react(post_id: str, body: ReactionRequest, request: Request):
    user_id = require_session(request)
    username = request.session.get("username", "")
    db = get_database()

    try:
        result = await react_to_post(db, post_id, user_id, body.reaction_type)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Thông báo cho chủ bài nếu là reaction mới (có my_reaction)
    if result.my_reaction:
        post = await db.posts.find_one(
            {"_id": ObjectId(post_id)}, {"user_id": 1}
        )
        if post and str(post["user_id"]) != user_id:
            await notify_new_reaction(
                str(post["user_id"]), post_id, username, body.reaction_type
            )

    return result


@router.get("/{post_id}/reactions", response_model=ReactionCountResponse)
async def reactions(post_id: str, request: Request):
    user_id = require_session(request)
    db = get_database()
    try:
        return await get_reaction_counts(db, post_id, user_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
