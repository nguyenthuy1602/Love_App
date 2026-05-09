from fastapi import APIRouter, HTTPException, Request, Query, UploadFile, File

from app.core.deps import require_session, require_session_full
from app.db.mongodb import get_database
from app.schemas.post import PostCreateRequest, PostResponse, FeedResponse
from app.services.post_service import create_post, get_post_by_id, get_feed, delete_post
from app.services.media_service import upload_media
from app.middleware.user_rate_limit import post_limiter

router = APIRouter(prefix="/posts", tags=["Posts"])


@router.post("/upload-media", status_code=200)
async def upload_post_media(request: Request, file: UploadFile = File(...)):
    """
    Upload ảnh hoặc video trước khi tạo bài viết.
    Trả về { url, media_type } để đính kèm vào PostCreateRequest.
    """
    user_id, _ = require_session_full(request)
    result = await upload_media(file, user_id, folder="posts")
    return result


@router.post("", response_model=PostResponse, status_code=201)
async def create_new_post(body: PostCreateRequest, request: Request):
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"create_new_post: content={body.content[:50]}... media_urls={body.media_urls} media_type={body.media_type}")
    
    user_id, username = require_session_full(request)
    post_limiter.check(user_id, "posts")

    db = get_database()
    # Lấy avatar_url từ user để đính vào bài đăng
    user_doc = await db.users.find_one(
        {"username": username}, {"avatar_url": 1}
    )
    avatar_url = user_doc.get("avatar_url") if user_doc else None

    try:
        return await create_post(db, user_id, username, body, avatar_url=avatar_url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/feed", response_model=FeedResponse)
async def feed(
    request: Request,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=50),
):
    user_id = require_session(request)
    db = get_database()
    return await get_feed(db, viewer_user_id=user_id, page=page, page_size=page_size)


@router.get("/{post_id}", response_model=PostResponse)
async def get_post(post_id: str, request: Request):
    user_id = require_session(request)
    db = get_database()
    try:
        return await get_post_by_id(db, post_id, viewer_user_id=user_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/{post_id}", status_code=204)
async def delete_my_post(post_id: str, request: Request):
    user_id = require_session(request)
    db = get_database()
    try:
        await delete_post(db, post_id, user_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
