from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.schemas.profile import ProfileResponse, ProfileUpdateRequest
from app.services.post_service import get_posts_by_user
from app.core.connection_manager import manager


async def get_profile(
    db: AsyncIOMotorDatabase, user_id: str, viewer_user_id: str = ""
) -> ProfileResponse:
    try:
        oid = ObjectId(user_id)
    except Exception:
        raise ValueError("Invalid user ID")

    doc = await db.users.find_one({"_id": oid})
    if not doc:
        raise ValueError("User not found")

    posts = await get_posts_by_user(db, user_id, viewer_user_id=viewer_user_id)

    return ProfileResponse(
        id=str(doc["_id"]),
        username=doc["username"],
        bio=doc.get("bio"),
        avatar_url=doc.get("avatar_url"),
        sentiment_profile=doc.get("sentiment_profile"),
        is_online=manager.is_online(user_id),
        created_at=doc["created_at"],
        posts=posts,
    )


async def update_profile(
    db: AsyncIOMotorDatabase, user_id: str, data: ProfileUpdateRequest
) -> ProfileResponse:
    try:
        oid = ObjectId(user_id)
    except Exception:
        raise ValueError("Invalid user ID")

    update_fields = {k: v for k, v in data.model_dump().items() if v is not None}
    if not update_fields:
        raise ValueError("No fields to update")

    result = await db.users.find_one_and_update(
        {"_id": oid},
        {"$set": update_fields},
        return_document=True,
    )
    if not result:
        raise ValueError("User not found")

    posts = await get_posts_by_user(db, user_id)

    return ProfileResponse(
        id=str(result["_id"]),
        username=result["username"],
        bio=result.get("bio"),
        avatar_url=result.get("avatar_url"),
        sentiment_profile=result.get("sentiment_profile"),
        is_online=manager.is_online(user_id),
        created_at=result["created_at"],
        posts=posts,
    )
