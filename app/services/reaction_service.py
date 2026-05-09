"""
Reaction Service
Mỗi user chỉ có 1 reaction cho mỗi bài viết (upsert).
Reaction count được lưu denormalized trong post document để tránh $lookup khi load feed.
"""

from datetime import datetime, timezone
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.schemas.reaction import ReactionType, ReactionCountResponse

VALID_TYPES = {r.value for r in ReactionType}


async def react_to_post(
    db: AsyncIOMotorDatabase,
    post_id: str,
    user_id: str,
    reaction_type: str,
) -> ReactionCountResponse:
    """
    Upsert reaction. Nếu user đã react cùng loại → xóa (toggle off).
    Nếu react khác loại → đổi reaction.
    """
    try:
        post_oid = ObjectId(post_id)
        user_oid = ObjectId(user_id)
    except Exception:
        raise ValueError("Invalid ID")

    if reaction_type not in VALID_TYPES:
        raise ValueError(f"Invalid reaction type: {reaction_type}")

    post = await db.posts.find_one({"_id": post_oid})
    if not post:
        raise ValueError("Post not found")

    existing = await db.reactions.find_one({
        "post_id": post_oid,
        "user_id": user_oid,
    })

    if existing and existing["reaction_type"] == reaction_type:
        # Toggle off — xóa reaction
        await db.reactions.delete_one({"_id": existing["_id"]})
        await db.posts.update_one(
            {"_id": post_oid},
            {"$inc": {f"reactions.{reaction_type}": -1}},
        )
    elif existing:
        # Đổi reaction cũ → mới
        old_type = existing["reaction_type"]
        await db.reactions.update_one(
            {"_id": existing["_id"]},
            {"$set": {"reaction_type": reaction_type, "updated_at": datetime.now(timezone.utc)}},
        )
        await db.posts.update_one(
            {"_id": post_oid},
            {"$inc": {f"reactions.{old_type}": -1, f"reactions.{reaction_type}": 1}},
        )
    else:
        # Reaction mới
        await db.reactions.insert_one({
            "post_id": post_oid,
            "user_id": user_oid,
            "reaction_type": reaction_type,
            "created_at": datetime.now(timezone.utc),
        })
        await db.posts.update_one(
            {"_id": post_oid},
            {"$inc": {f"reactions.{reaction_type}": 1}},
        )

    # Trả về counts mới nhất
    updated = await db.posts.find_one({"_id": post_oid}, {"reactions": 1})
    r = updated.get("reactions", {})

    my_reaction_doc = await db.reactions.find_one({
        "post_id": post_oid, "user_id": user_oid
    })

    return ReactionCountResponse(
        post_id=post_id,
        heart=r.get("heart", 0),
        sad=r.get("sad", 0),
        wow=r.get("wow", 0),
        haha=r.get("haha", 0),
        fire=r.get("fire", 0),
        my_reaction=my_reaction_doc["reaction_type"] if my_reaction_doc else None,
    )


async def get_reaction_counts(
    db: AsyncIOMotorDatabase, post_id: str, user_id: str = ""
) -> ReactionCountResponse:
    try:
        post_oid = ObjectId(post_id)
    except Exception:
        raise ValueError("Invalid post ID")

    post = await db.posts.find_one({"_id": post_oid}, {"reactions": 1})
    if not post:
        raise ValueError("Post not found")

    r = post.get("reactions", {})
    my_reaction = None
    if user_id:
        doc = await db.reactions.find_one({
            "post_id": post_oid, "user_id": ObjectId(user_id)
        })
        my_reaction = doc["reaction_type"] if doc else None

    return ReactionCountResponse(
        post_id=post_id,
        heart=r.get("heart", 0),
        sad=r.get("sad", 0),
        wow=r.get("wow", 0),
        haha=r.get("haha", 0),
        fire=r.get("fire", 0),
        my_reaction=my_reaction,
    )
