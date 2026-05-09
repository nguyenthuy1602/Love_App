"""
Matching Service — Epic 3
Ghép đôi dựa trên sentiment (Gemini-powered) hoặc ngẫu nhiên.
Có kiểm tra block, tính compatibility score, hiển thị online status.
"""

import random
from datetime import datetime, timezone
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.schemas.match import MatchResponse, MatchStatus
from app.core.connection_manager import manager

# Cặp sentiment bổ trợ nhau (người buồn gặp người vui)
COMPLEMENTARY = {
    "positive": ["positive", "neutral"],
    "negative": ["positive", "neutral"],
    "neutral":  ["positive", "neutral", "negative"],
}


def _serialize_match(doc: dict) -> MatchResponse:
    partner_id = str(doc.get("user2_id", ""))
    return MatchResponse(
        id=str(doc["_id"]),
        user1_id=str(doc["user1_id"]),
        user2_id=partner_id,
        user1_username=doc.get("user1_username", ""),
        user2_username=doc.get("user2_username", ""),
        user2_bio=doc.get("user2_bio"),
        user2_avatar_url=doc.get("user2_avatar_url"),
        user2_sentiment=doc.get("user2_sentiment"),
        partner_is_online=manager.is_online(partner_id),
        status=doc["status"],
        created_at=doc["created_at"],
    )


async def _get_excluded_user_ids(
    db: AsyncIOMotorDatabase, user_id: str
) -> set:
    oid = ObjectId(user_id)

    # Đã match/skip trước đây
    cursor = db.matches.find({
        "$or": [{"user1_id": oid}, {"user2_id": oid}]
    })
    docs = await cursor.to_list(length=500)
    excluded = {user_id}
    for doc in docs:
        excluded.add(str(doc["user1_id"]))
        excluded.add(str(doc["user2_id"]))

    # Đã block hoặc bị block
    block_cursor = db.blocks.find({
        "$or": [{"blocker_id": oid}, {"blocked_id": oid}]
    })
    block_docs = await block_cursor.to_list(length=200)
    for doc in block_docs:
        excluded.add(str(doc["blocker_id"]))
        excluded.add(str(doc["blocked_id"]))

    return excluded


async def _create_match_doc(
    db: AsyncIOMotorDatabase,
    user1_id: str,
    user1_username: str,
    target_user: dict,
) -> MatchResponse:
    doc = {
        "user1_id": ObjectId(user1_id),
        "user1_username": user1_username,
        "user2_id": target_user["_id"],
        "user2_username": target_user["username"],
        "user2_bio": target_user.get("bio"),
        "user2_avatar_url": target_user.get("avatar_url"),
        "user2_sentiment": target_user.get("sentiment_profile"),
        "status": MatchStatus.PENDING,
        "created_at": datetime.now(timezone.utc),
    }
    result = await db.matches.insert_one(doc)
    doc["_id"] = result.inserted_id
    return _serialize_match(doc)


async def suggest_by_sentiment(
    db: AsyncIOMotorDatabase, user_id: str
) -> MatchResponse:
    """
    Gợi ý dựa trên sentiment tương thích.
    Ưu tiên: cùng sentiment → sentiment bổ trợ → ngẫu nhiên.
    """
    oid = ObjectId(user_id)
    me = await db.users.find_one({"_id": oid})
    if not me:
        raise ValueError("User not found")

    my_sentiment = me.get("sentiment_profile", "neutral")
    excluded = await _get_excluded_user_ids(db, user_id)
    excluded_oids = [ObjectId(uid) for uid in excluded if ObjectId.is_valid(uid)]

    # 1. Cùng sentiment
    candidates = await db.users.find({
        "_id": {"$nin": excluded_oids},
        "sentiment_profile": my_sentiment,
    }).to_list(length=50)

    # 2. Sentiment bổ trợ
    if not candidates:
        compatible = COMPLEMENTARY.get(my_sentiment, ["neutral"])
        candidates = await db.users.find({
            "_id": {"$nin": excluded_oids},
            "sentiment_profile": {"$in": compatible},
        }).to_list(length=50)

    # 3. Fallback ngẫu nhiên
    if not candidates:
        candidates = await db.users.find(
            {"_id": {"$nin": excluded_oids}}
        ).to_list(length=50)

    if not candidates:
        raise ValueError("No available users to match")

    target = random.choice(candidates)
    return await _create_match_doc(db, user_id, me["username"], target)


async def suggest_random(
    db: AsyncIOMotorDatabase, user_id: str
) -> MatchResponse:
    excluded = await _get_excluded_user_ids(db, user_id)
    excluded_oids = [ObjectId(uid) for uid in excluded if ObjectId.is_valid(uid)]

    candidates = await db.users.find(
        {"_id": {"$nin": excluded_oids}}
    ).to_list(length=100)

    if not candidates:
        raise ValueError("No available users to match")

    target = random.choice(candidates)
    me = await db.users.find_one({"_id": ObjectId(user_id)})
    username = me["username"] if me else ""
    return await _create_match_doc(db, user_id, username, target)


async def accept_match(
    db: AsyncIOMotorDatabase, match_id: str, user_id: str
) -> MatchResponse:
    try:
        oid = ObjectId(match_id)
    except Exception:
        raise ValueError("Invalid match ID")

    doc = await db.matches.find_one({"_id": oid})
    if not doc:
        raise ValueError("Match not found")
    if str(doc["user1_id"]) != user_id:
        raise PermissionError("Not your match")
    if doc["status"] != MatchStatus.PENDING:
        raise ValueError(f"Match is already {doc['status']}")

    updated = await db.matches.find_one_and_update(
        {"_id": oid},
        {"$set": {"status": MatchStatus.ACCEPTED}},
        return_document=True,
    )
    return _serialize_match(updated)


async def skip_match(
    db: AsyncIOMotorDatabase, match_id: str, user_id: str
) -> None:
    try:
        oid = ObjectId(match_id)
    except Exception:
        raise ValueError("Invalid match ID")

    doc = await db.matches.find_one({"_id": oid})
    if not doc:
        raise ValueError("Match not found")
    if str(doc["user1_id"]) != user_id:
        raise PermissionError("Not your match")

    await db.matches.update_one(
        {"_id": oid},
        {"$set": {"status": MatchStatus.SKIPPED}},
    )


async def get_my_matches(
    db: AsyncIOMotorDatabase, user_id: str
) -> list[MatchResponse]:
    oid = ObjectId(user_id)
    cursor = db.matches.find({
        "$or": [{"user1_id": oid}, {"user2_id": oid}],
        "status": MatchStatus.ACCEPTED,
    }).sort("created_at", -1)
    docs = await cursor.to_list(length=100)
    return [_serialize_match(d) for d in docs]
