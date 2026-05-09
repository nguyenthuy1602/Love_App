from datetime import datetime, timezone
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.schemas.post import PostCreateRequest, PostResponse, FeedResponse, ReactionSummary
from app.services.sentiment_service import analyze_sentiment, update_user_sentiment_profile


def _serialize_post(doc: dict, my_reaction: str | None = None) -> PostResponse:
    reactions_raw = doc.get("reactions", {})
    return PostResponse(
        id=str(doc["_id"]),
        user_id=str(doc["user_id"]),
        username=doc.get("username", ""),
        avatar_url=doc.get("avatar_url"),
        content=doc["content"],
        media_urls=doc.get("media_urls", []),
        media_type=doc.get("media_type"),
        sentiment_score=doc.get("sentiment_score"),
        sentiment_confidence=doc.get("sentiment_confidence"),
        reactions=ReactionSummary(
            heart=reactions_raw.get("heart", 0),
            sad=reactions_raw.get("sad", 0),
            wow=reactions_raw.get("wow", 0),
            haha=reactions_raw.get("haha", 0),
            fire=reactions_raw.get("fire", 0),
            my_reaction=my_reaction,
        ),
        comment_count=doc.get("comment_count", 0),
        created_at=doc["created_at"],
    )


async def _get_my_reactions(
    db: AsyncIOMotorDatabase, post_ids: list, user_id: str
) -> dict[str, str]:
    """Lấy reaction của user hiện tại cho danh sách bài viết."""
    if not post_ids or not user_id:
        return {}
    oids = [ObjectId(pid) if isinstance(pid, str) else pid for pid in post_ids]
    cursor = db.reactions.find({
        "post_id": {"$in": oids},
        "user_id": ObjectId(user_id),
    })
    docs = await cursor.to_list(length=len(post_ids))
    return {str(d["post_id"]): d["reaction_type"] for d in docs}


async def create_post(
    db: AsyncIOMotorDatabase,
    user_id: str,
    username: str,
    data: PostCreateRequest,
    avatar_url: str | None = None,
) -> PostResponse:
    sentiment, confidence = await analyze_sentiment(data.content)

    doc = {
        "user_id": ObjectId(user_id),
        "username": username,
        "avatar_url": avatar_url,
        "content": data.content,
        "media_urls": data.media_urls,
        "media_type": data.media_type,
        "sentiment_score": sentiment,
        "sentiment_confidence": confidence,
        "reactions": {"heart": 0, "sad": 0, "wow": 0, "haha": 0, "fire": 0},
        "comment_count": 0,
        "created_at": datetime.now(timezone.utc),
    }
    result = await db.posts.insert_one(doc)
    doc["_id"] = result.inserted_id

    await update_user_sentiment_profile(db, user_id)
    return _serialize_post(doc)


async def get_post_by_id(
    db: AsyncIOMotorDatabase, post_id: str, viewer_user_id: str = ""
) -> PostResponse:
    try:
        oid = ObjectId(post_id)
    except Exception:
        raise ValueError("Invalid post ID")

    doc = await db.posts.find_one({"_id": oid})
    if not doc:
        raise ValueError("Post not found")

    my_reactions = await _get_my_reactions(db, [oid], viewer_user_id)
    return _serialize_post(doc, my_reactions.get(post_id))


async def get_feed(
    db: AsyncIOMotorDatabase,
    viewer_user_id: str = "",
    page: int = 1,
    page_size: int = 20,
) -> FeedResponse:
    skip = (page - 1) * page_size
    cursor = db.posts.find().sort("created_at", -1).skip(skip).limit(page_size)
    docs = await cursor.to_list(length=page_size)
    total = await db.posts.count_documents({})

    post_ids = [d["_id"] for d in docs]
    my_reactions = await _get_my_reactions(db, post_ids, viewer_user_id)

    return FeedResponse(
        posts=[_serialize_post(d, my_reactions.get(str(d["_id"]))) for d in docs],
        total=total,
        page=page,
        page_size=page_size,
    )


async def get_posts_by_user(
    db: AsyncIOMotorDatabase, user_id: str, viewer_user_id: str = ""
) -> list[PostResponse]:
    try:
        oid = ObjectId(user_id)
    except Exception:
        raise ValueError("Invalid user ID")

    cursor = db.posts.find({"user_id": oid}).sort("created_at", -1)
    docs = await cursor.to_list(length=100)

    post_ids = [d["_id"] for d in docs]
    my_reactions = await _get_my_reactions(db, post_ids, viewer_user_id)

    return [_serialize_post(d, my_reactions.get(str(d["_id"]))) for d in docs]


async def delete_post(
    db: AsyncIOMotorDatabase, post_id: str, requester_user_id: str
) -> None:
    try:
        oid = ObjectId(post_id)
    except Exception:
        raise ValueError("Invalid post ID")

    doc = await db.posts.find_one({"_id": oid})
    if not doc:
        raise ValueError("Post not found")
    if str(doc["user_id"]) != requester_user_id:
        raise PermissionError("You can only delete your own posts")

    await db.posts.delete_one({"_id": oid})
    # Dọn reactions và comments liên quan
    await db.reactions.delete_many({"post_id": oid})
    await db.comments.delete_many({"post_id": oid})
