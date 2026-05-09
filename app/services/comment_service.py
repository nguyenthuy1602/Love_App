"""
Comment Service
Bình luận bài viết. comment_count được lưu denormalized trong post document.
"""

from datetime import datetime, timezone
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.schemas.comment import CommentResponse, CommentListResponse


def _serialize_comment(doc: dict) -> CommentResponse:
    return CommentResponse(
        id=str(doc["_id"]),
        post_id=str(doc["post_id"]),
        user_id=str(doc["user_id"]),
        username=doc.get("username", ""),
        avatar_url=doc.get("avatar_url"),
        content=doc["content"],
        created_at=doc["created_at"],
    )


async def add_comment(
    db: AsyncIOMotorDatabase,
    post_id: str,
    user_id: str,
    username: str,
    content: str,
    avatar_url: str | None = None,
) -> CommentResponse:
    try:
        post_oid = ObjectId(post_id)
        user_oid = ObjectId(user_id)
    except Exception:
        raise ValueError("Invalid ID")

    post = await db.posts.find_one({"_id": post_oid}, {"_id": 1})
    if not post:
        raise ValueError("Post not found")

    doc = {
        "post_id": post_oid,
        "user_id": user_oid,
        "username": username,
        "avatar_url": avatar_url,
        "content": content,
        "created_at": datetime.now(timezone.utc),
    }
    result = await db.comments.insert_one(doc)
    doc["_id"] = result.inserted_id

    # Cập nhật count denormalized
    await db.posts.update_one({"_id": post_oid}, {"$inc": {"comment_count": 1}})

    return _serialize_comment(doc)


async def get_comments(
    db: AsyncIOMotorDatabase,
    post_id: str,
    page: int = 1,
    page_size: int = 20,
) -> CommentListResponse:
    try:
        post_oid = ObjectId(post_id)
    except Exception:
        raise ValueError("Invalid post ID")

    skip = (page - 1) * page_size
    cursor = (
        db.comments.find({"post_id": post_oid})
        .sort("created_at", 1)
        .skip(skip)
        .limit(page_size)
    )
    docs = await cursor.to_list(length=page_size)
    total = await db.comments.count_documents({"post_id": post_oid})

    return CommentListResponse(
        post_id=post_id,
        comments=[_serialize_comment(d) for d in docs],
        total=total,
    )


async def delete_comment(
    db: AsyncIOMotorDatabase, comment_id: str, requester_user_id: str
) -> None:
    try:
        oid = ObjectId(comment_id)
    except Exception:
        raise ValueError("Invalid comment ID")

    doc = await db.comments.find_one({"_id": oid})
    if not doc:
        raise ValueError("Comment not found")
    if str(doc["user_id"]) != requester_user_id:
        raise PermissionError("You can only delete your own comments")

    await db.comments.delete_one({"_id": oid})
    await db.posts.update_one(
        {"_id": doc["post_id"]},
        {"$inc": {"comment_count": -1}},
    )
