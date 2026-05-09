"""
MongoDB Index Setup
Chạy một lần khi app khởi động. Idempotent — safe to re-run.
"""

from app.db.mongodb import get_database
import logging

logger = logging.getLogger(__name__)


async def create_indexes():
    db = get_database()

    # ── users ─────────────────────────────────────────────────
    await db.users.create_index("username", unique=True)
    await db.users.create_index("sentiment_profile")

    # ── posts ─────────────────────────────────────────────────
    await db.posts.create_index("user_id")
    await db.posts.create_index([("created_at", -1)])          # feed sort
    await db.posts.create_index("sentiment_score")

    # ── matches ───────────────────────────────────────────────
    await db.matches.create_index("user1_id")
    await db.matches.create_index("user2_id")
    await db.matches.create_index([("user1_id", 1), ("user2_id", 1)])
    await db.matches.create_index("status")

    # ── messages ──────────────────────────────────────────────
    await db.messages.create_index("match_id")
    await db.messages.create_index([("match_id", 1), ("created_at", 1)])

    # ── reactions ─────────────────────────────────────────────
    await db.reactions.create_index(
        [("post_id", 1), ("user_id", 1)], unique=True        # 1 reaction/user/bài
    )
    await db.reactions.create_index("post_id")

    # ── comments ──────────────────────────────────────────────
    await db.comments.create_index("post_id")
    await db.comments.create_index([("post_id", 1), ("created_at", 1)])

    # ── blocks ────────────────────────────────────────────────
    await db.blocks.create_index([("blocker_id", 1), ("blocked_id", 1)], unique=True)
    await db.blocks.create_index("blocker_id")

    # ── reports ───────────────────────────────────────────────
    await db.reports.create_index([("reporter_id", 1), ("target_id", 1)])
    await db.reports.create_index("status")

    logger.info("✅ MongoDB indexes created/verified")
