"""
Moderation Service
Block/unblock user, report user/post, unmatch.
"""

from datetime import datetime, timezone
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.schemas.moderation import BlockResponse, ReportResponse, ReportRequest
from app.schemas.match import MatchStatus


# ── Block ─────────────────────────────────────────────────────

async def block_user(
    db: AsyncIOMotorDatabase, blocker_id: str, blocked_id: str
) -> BlockResponse:
    if blocker_id == blocked_id:
        raise ValueError("Cannot block yourself")

    try:
        blocker_oid = ObjectId(blocker_id)
        blocked_oid = ObjectId(blocked_id)
    except Exception:
        raise ValueError("Invalid user ID")

    target = await db.users.find_one({"_id": blocked_oid}, {"username": 1})
    if not target:
        raise ValueError("User not found")

    existing = await db.blocks.find_one({
        "blocker_id": blocker_oid, "blocked_id": blocked_oid
    })
    if existing:
        raise ValueError("Already blocked")

    doc = {
        "blocker_id": blocker_oid,
        "blocked_id": blocked_oid,
        "created_at": datetime.now(timezone.utc),
    }
    await db.blocks.insert_one(doc)

    # Hủy tất cả match đang active giữa 2 người
    await db.matches.update_many(
        {
            "status": MatchStatus.ACCEPTED,
            "$or": [
                {"user1_id": blocker_oid, "user2_id": blocked_oid},
                {"user1_id": blocked_oid, "user2_id": blocker_oid},
            ],
        },
        {"$set": {"status": MatchStatus.UNMATCHED}},
    )

    return BlockResponse(
        blocker_id=blocker_id,
        blocked_id=blocked_id,
        blocked_username=target["username"],
        created_at=doc["created_at"],
    )


async def unblock_user(
    db: AsyncIOMotorDatabase, blocker_id: str, blocked_id: str
) -> None:
    try:
        blocker_oid = ObjectId(blocker_id)
        blocked_oid = ObjectId(blocked_id)
    except Exception:
        raise ValueError("Invalid user ID")

    result = await db.blocks.delete_one({
        "blocker_id": blocker_oid, "blocked_id": blocked_oid
    })
    if result.deleted_count == 0:
        raise ValueError("Block not found")


async def get_blocked_users(
    db: AsyncIOMotorDatabase, user_id: str
) -> list[dict]:
    oid = ObjectId(user_id)
    cursor = db.blocks.find({"blocker_id": oid}).sort("created_at", -1)
    docs = await cursor.to_list(length=200)

    blocked_ids = [d["blocked_id"] for d in docs]
    users = await db.users.find(
        {"_id": {"$in": blocked_ids}}, {"username": 1, "avatar_url": 1}
    ).to_list(length=200)
    user_map = {str(u["_id"]): u for u in users}

    result = []
    for doc in docs:
        uid = str(doc["blocked_id"])
        u = user_map.get(uid, {})
        result.append({
            "blocked_id": uid,
            "username": u.get("username", ""),
            "avatar_url": u.get("avatar_url"),
            "blocked_at": doc["created_at"],
        })
    return result


async def is_blocked(
    db: AsyncIOMotorDatabase, user_a: str, user_b: str
) -> bool:
    """Kiểm tra có block theo chiều nào không."""
    try:
        oid_a = ObjectId(user_a)
        oid_b = ObjectId(user_b)
    except Exception:
        return False

    doc = await db.blocks.find_one({
        "$or": [
            {"blocker_id": oid_a, "blocked_id": oid_b},
            {"blocker_id": oid_b, "blocked_id": oid_a},
        ]
    })
    return doc is not None


# ── Report ────────────────────────────────────────────────────

async def report_target(
    db: AsyncIOMotorDatabase, reporter_id: str, data: ReportRequest
) -> ReportResponse:
    if reporter_id == data.target_id:
        raise ValueError("Cannot report yourself")

    try:
        reporter_oid = ObjectId(reporter_id)
        target_oid   = ObjectId(data.target_id)
    except Exception:
        raise ValueError("Invalid ID")

    # Kiểm tra target tồn tại
    collection = "users" if data.target_type == "user" else "posts"
    target = await db[collection].find_one({"_id": target_oid}, {"_id": 1})
    if not target:
        raise ValueError(f"{data.target_type.capitalize()} not found")

    # Chặn report trùng trong 24h
    from datetime import timedelta
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    existing = await db.reports.find_one({
        "reporter_id": reporter_oid,
        "target_id": target_oid,
        "created_at": {"$gte": cutoff},
    })
    if existing:
        raise ValueError("You have already reported this recently")

    doc = {
        "reporter_id": reporter_oid,
        "target_id": target_oid,
        "target_type": data.target_type,
        "reason": data.reason,
        "description": data.description,
        "status": "pending",
        "created_at": datetime.now(timezone.utc),
    }
    result = await db.reports.insert_one(doc)
    doc["_id"] = result.inserted_id

    return ReportResponse(
        id=str(doc["_id"]),
        reporter_id=reporter_id,
        target_id=data.target_id,
        target_type=data.target_type,
        reason=data.reason,
        status="pending",
        created_at=doc["created_at"],
    )


# ── Unmatch ───────────────────────────────────────────────────

async def unmatch(
    db: AsyncIOMotorDatabase, match_id: str, user_id: str
) -> None:
    try:
        match_oid = ObjectId(match_id)
        user_oid  = ObjectId(user_id)
    except Exception:
        raise ValueError("Invalid ID")

    doc = await db.matches.find_one({"_id": match_oid})
    if not doc:
        raise ValueError("Match not found")

    # Cả 2 người đều có thể unmatch
    if str(doc["user1_id"]) != user_id and str(doc["user2_id"]) != user_id:
        raise PermissionError("Not your match")

    if doc["status"] != MatchStatus.ACCEPTED:
        raise ValueError("Can only unmatch an accepted match")

    await db.matches.update_one(
        {"_id": match_oid},
        {"$set": {"status": MatchStatus.UNMATCHED, "unmatched_by": user_oid}},
    )
