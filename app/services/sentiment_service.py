"""
Sentiment Analysis Service — Gemini AI
Phân tích cảm xúc bài viết bằng Gemini API.
Fallback về rule-based nếu Gemini không khả dụng hoặc key chưa cấu hình.
"""

import json
import logging
import httpx
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId

from app.core.config import settings

logger = logging.getLogger(__name__)

# ── Rule-based fallback ───────────────────────────────────────

POSITIVE_KEYWORDS = {
    "vui", "hạnh phúc", "tuyệt", "tuyệt vời", "yêu", "thích", "tốt",
    "hay", "đẹp", "xinh", "cười", "haha", "hehe", "ổn", "oke", "ok",
    "thành công", "hoàn hảo", "phấn khích", "tự hào", "hy vọng", "yêu đời",
    "vui vẻ", "hài lòng", "biết ơn", "cảm ơn", "wonderful", "amazing",
    "happy", "love", "great", "good", "nice", "awesome", "excellent",
    "fantastic", "joy", "excited", "glad", "cheerful", "positive",
}

NEGATIVE_KEYWORDS = {
    "buồn", "chán", "tệ", "khóc", "đau", "mệt", "stress", "áp lực",
    "thất bại", "khó", "ghét", "sợ", "lo", "lo lắng", "tức", "giận",
    "cô đơn", "nhớ", "tiếc", "thất vọng", "bực", "khổ", "tuyệt vọng",
    "không ổn", "chán nản", "mệt mỏi", "đau khổ",
    "sad", "hate", "bad", "terrible", "awful", "depressed", "lonely",
    "angry", "frustrated", "anxious", "stressed", "tired", "exhausted",
    "miserable", "unhappy", "disappointed", "hopeless", "upset",
}


def _rule_based_sentiment(content: str) -> tuple[str, float]:
    text = content.lower()
    words = set(text.replace(",", " ").replace(".", " ").replace("!", " ").split())
    pos = len(words & POSITIVE_KEYWORDS)
    neg = len(words & NEGATIVE_KEYWORDS)
    total = pos + neg
    if total == 0:
        return "neutral", 0.5
    if pos > neg:
        return "positive", round(pos / total, 2)
    if neg > pos:
        return "negative", round(neg / total, 2)
    return "neutral", 0.5


# ── Gemini API ────────────────────────────────────────────────

GEMINI_PROMPT = """Bạn là một chuyên gia phân tích cảm xúc văn bản tiếng Việt và tiếng Anh.

Phân tích cảm xúc của đoạn văn sau và trả về JSON với định dạng chính xác:
{{"sentiment": "positive" | "negative" | "neutral", "confidence": <số thực 0.0-1.0>, "reason": "<giải thích ngắn gọn 1 câu>"}}

Quy tắc:
- positive: nội dung vui vẻ, lạc quan, tích cực, hạnh phúc, tự hào
- negative: nội dung buồn bã, tức giận, lo lắng, thất vọng, tiêu cực
- neutral: thông tin trung tính, không rõ cảm xúc
- confidence: độ chắc chắn của phán đoán (0.5 = không chắc, 1.0 = rất chắc)
- Chỉ trả về JSON, không có markdown, không có giải thích thêm

Văn bản cần phân tích:
\"\"\"{content}\"\"\""""


async def _gemini_sentiment(content: str) -> tuple[str, float] | None:
    """
    Gọi Gemini API để phân tích sentiment.
    Trả về (sentiment, confidence) hoặc None nếu lỗi.
    """
    if not settings.gemini_api_key:
        return None

    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{settings.gemini_model}:generateContent"
        f"?key={settings.gemini_api_key}"
    )
    payload = {
        "contents": [{"parts": [{"text": GEMINI_PROMPT.format(content=content[:800])}]}],
        "generationConfig": {
            "temperature": 0.1,
            "maxOutputTokens": 120,
            "responseMimeType": "application/json",
        },
    }

    try:
        async with httpx.AsyncClient(timeout=settings.gemini_timeout) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()

        raw = data["candidates"][0]["content"]["parts"][0]["text"]
        result = json.loads(raw)

        sentiment = result.get("sentiment", "neutral")
        if sentiment not in ("positive", "negative", "neutral"):
            sentiment = "neutral"
        confidence = float(result.get("confidence", 0.5))
        confidence = max(0.0, min(1.0, confidence))

        return sentiment, confidence

    except Exception as e:
        logger.warning(f"Gemini sentiment failed: {e} — falling back to rule-based")
        return None


# ── Public API ────────────────────────────────────────────────

async def analyze_sentiment(content: str) -> tuple[str, float]:
    """
    Phân tích sentiment. Ưu tiên Gemini, fallback rule-based.
    Trả về (sentiment, confidence).
    """
    result = await _gemini_sentiment(content)
    if result:
        return result
    return _rule_based_sentiment(content)


async def update_user_sentiment_profile(
    db: AsyncIOMotorDatabase, user_id: str
) -> str:
    """
    Tính lại sentiment_profile của user dựa trên 10 bài viết gần nhất.
    Weighted: bài mới hơn có trọng số cao hơn.
    """
    oid = ObjectId(user_id)
    cursor = db.posts.find(
        {"user_id": oid, "sentiment_score": {"$ne": None}}
    ).sort("created_at", -1).limit(10)
    recent_posts = await cursor.to_list(length=10)

    if not recent_posts:
        return "neutral"

    # Weighted sum: bài mới nhất trọng số 10, cũ nhất trọng số 1
    counts = {"positive": 0.0, "negative": 0.0, "neutral": 0.0}
    total_posts = len(recent_posts)
    for i, post in enumerate(recent_posts):
        score = post.get("sentiment_score", "neutral")
        weight = (total_posts - i)              # newest = highest weight
        confidence = post.get("sentiment_confidence", 0.5) or 0.5
        counts[score] = counts.get(score, 0.0) + weight * confidence

    dominant = max(counts, key=counts.get)
    await db.users.update_one(
        {"_id": oid},
        {"$set": {"sentiment_profile": dominant}}
    )
    return dominant
