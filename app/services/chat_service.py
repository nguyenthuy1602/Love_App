from datetime import datetime, timezone
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.schemas.message import MessageResponse, ChatHistoryResponse


def _serialize_message(doc: dict) -> MessageResponse:
    return MessageResponse(
        id=str(doc["_id"]),
        match_id=str(doc["match_id"]),
        sender_id=str(doc["sender_id"]),
        sender_username=doc.get("sender_username", ""),
        content=doc["content"],
        created_at=doc["created_at"],
    )


async def save_message(
    db: AsyncIOMotorDatabase,
    match_id: str,
    sender_id: str,
    sender_username: str,
    content: str,
) -> MessageResponse:
    doc = {
        "match_id": ObjectId(match_id),
        "sender_id": ObjectId(sender_id),
        "sender_username": sender_username,
        "content": content,
        "created_at": datetime.now(timezone.utc),
    }
    result = await db.messages.insert_one(doc)
    doc["_id"] = result.inserted_id
    return _serialize_message(doc)


async def get_chat_history(
    db: AsyncIOMotorDatabase,
    match_id: str,
    limit: int = 50,
    before_id: str | None = None,   # cursor: lấy tin nhắn cũ hơn ObjectId này
) -> ChatHistoryResponse:
    try:
        oid = ObjectId(match_id)
    except Exception:
        raise ValueError("Invalid match ID")

    query: dict = {"match_id": oid}
    if before_id:
        try:
            query["_id"] = {"$lt": ObjectId(before_id)}
        except Exception:
            pass  # bỏ qua cursor không hợp lệ

    cursor = (
        db.messages.find(query)
        .sort("created_at", -1)      # mới nhất trước để lấy đúng page
        .limit(limit + 1)            # lấy thêm 1 để biết có trang tiếp không
    )
    docs = await cursor.to_list(length=limit + 1)

    has_more = len(docs) > limit
    if has_more:
        docs = docs[:limit]

    docs.reverse()   # trả về theo thứ tự cũ → mới cho UI

    next_cursor = str(docs[0]["_id"]) if has_more and docs else None

    return ChatHistoryResponse(
        match_id=match_id,
        messages=[_serialize_message(d) for d in docs],
        has_more=has_more,
        next_cursor=next_cursor,
    )


async def verify_match_access(
    db: AsyncIOMotorDatabase, match_id: str, user_id: str
) -> bool:
    try:
        match_oid = ObjectId(match_id)
        user_oid  = ObjectId(user_id)
    except Exception:
        return False

    match = await db.matches.find_one({
        "_id": match_oid,
        "status": "accepted",
        "$or": [
            {"user1_id": user_oid},
            {"user2_id": user_oid},
        ],
    })
    return match is not None
