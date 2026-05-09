from datetime import datetime, timezone
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.security import hash_password, verify_password
from app.schemas.user import UserRegisterRequest, UserResponse


def _serialize_user(doc: dict, is_online: bool = False) -> UserResponse:
    return UserResponse(
        id=str(doc["_id"]),
        username=doc["username"],
        bio=doc.get("bio"),
        avatar_url=doc.get("avatar_url"),
        sentiment_profile=doc.get("sentiment_profile"),
        is_online=is_online,
        created_at=doc["created_at"],
    )


async def register_user(
    db: AsyncIOMotorDatabase, data: UserRegisterRequest
) -> UserResponse:
    existing = await db.users.find_one({"username": data.username})
    if existing:
        raise ValueError("Username already exists")

    doc = {
        "username": data.username,
        "password_hash": hash_password(data.password),
        "bio": data.bio,
        "avatar_url": None,
        "sentiment_profile": None,
        "created_at": datetime.now(timezone.utc),
    }
    result = await db.users.insert_one(doc)
    doc["_id"] = result.inserted_id
    return _serialize_user(doc)


async def login_user(
    db: AsyncIOMotorDatabase, username: str, password: str
) -> UserResponse:
    doc = await db.users.find_one({"username": username})
    if not doc or not verify_password(password, doc["password_hash"]):
        raise ValueError("Invalid username or password")
    return _serialize_user(doc)


async def get_user_by_id(
    db: AsyncIOMotorDatabase, user_id: str, is_online: bool = False
) -> UserResponse:
    try:
        oid = ObjectId(user_id)
    except Exception:
        raise ValueError("Invalid user ID")

    doc = await db.users.find_one({"_id": oid})
    if not doc:
        raise ValueError("User not found")
    return _serialize_user(doc, is_online=is_online)


async def update_user(
    db: AsyncIOMotorDatabase,
    user_id: str,
    bio: str | None = None,
    avatar_url: str | None = None,
) -> UserResponse:
    try:
        oid = ObjectId(user_id)
    except Exception:
        raise ValueError("Invalid user ID")

    fields: dict = {}
    if bio is not None:
        fields["bio"] = bio
    if avatar_url is not None:
        fields["avatar_url"] = avatar_url

    if not fields:
        raise ValueError("No fields to update")

    result = await db.users.find_one_and_update(
        {"_id": oid},
        {"$set": fields},
        return_document=True,
    )
    if not result:
        raise ValueError("User not found")
    return _serialize_user(result)
