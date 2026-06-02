"""
Sentiment Analysis Service — Aura / external AI layer
Phân tích cảm xúc bài viết bằng external AI layer hoặc Gemini API.
Fallback về rule-based nếu không có external AI và Gemini không khả dụng.
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

# Map common emotion labels from external services to our 3 sentiment classes
EMOTION_TO_SENTIMENT = {
    "joy": "positive",
    "happy": "positive",
    "happiness": "positive",
    "excited": "positive",
    "love": "positive",
    "sadness": "negative",
    "sad": "negative",
    "anger": "negative",
    "angry": "negative",
    "fear": "negative",
    "anxiety": "negative",
    "disgust": "negative",
    "neutral": "neutral",
    "calm": "neutral",
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
    Legacy fallback: gọi Gemini API chỉ khi external AI layer không khả dụng.
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
        logger.warning(f"Aura sentiment (Gemini fallback) failed: {e} — falling back to rule-based")
        return None


async def _external_ai_sentiment(content: str) -> tuple[str, float] | None:
    """
    Gọi external AI layer nếu `settings.ai_sentiment_api_url` được cấu hình.
    Kỳ vọng response trả về JSON chứa `sentiment` và `confidence` (linh hoạt với nhiều trường tên khác).
    Trả về (sentiment, confidence) hoặc None nếu lỗi.
    """
    if not settings.ai_sentiment_api_url:
        return None

    from urllib.parse import urlparse

    url = settings.ai_sentiment_api_url.strip()
    parsed = urlparse(url)
    if not parsed.path or parsed.path == "/":
        url = url.rstrip("/") + "/predict"

    headers = {"Content-Type": "application/json"}
    if settings.ai_sentiment_api_key:
        headers["Authorization"] = f"Bearer {settings.ai_sentiment_api_key}"

    payload = {"text": content}

    try:
        async with httpx.AsyncClient(timeout=getattr(settings, "gemini_timeout", 8)) as client:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
        logger.info("External AI sentiment call success: url=%s status=%s", url, resp.status_code)

        # Flexible parsing: tìm `sentiment` và `confidence` ở nhiều vị trí
        sentiment = None
        confidence = None
        if isinstance(data, dict):
            sentiment = data.get("sentiment") or data.get("label") or data.get("prediction")
            # some services return an `emotion` field like "Sadness" — map it
            emotion = data.get("emotion")
            status = data.get("status")
            if not sentiment and emotion:
                mapped = EMOTION_TO_SENTIMENT.get(str(emotion).strip().lower())
                if mapped:
                    sentiment = mapped
            # if response includes nested objects, try to extract from them
            confidence = data.get("confidence") or data.get("score") or data.get("probability")
            # kiểm tra các nhánh khác
            for key in ("result", "data", "prediction"):
                if not sentiment and key in data and isinstance(data[key], dict):
                    sentiment = sentiment or data[key].get("sentiment")
                    confidence = confidence or data[key].get("confidence")
                    if not sentiment and data[key].get("emotion"):
                        mapped = EMOTION_TO_SENTIMENT.get(str(data[key].get("emotion")).strip().lower())
                        if mapped:
                            sentiment = mapped

            # if top-level status exists and is not success, treat as failure
            if status and isinstance(status, str) and status.strip().lower() != "success":
                return None

        if isinstance(sentiment, str):
            sentiment = sentiment.strip().lower()
            if sentiment not in ("positive", "negative", "neutral"):
                # map một vài nhãn hay gặp
                if sentiment.startswith("pos"):
                    sentiment = "positive"
                elif sentiment.startswith("neg"):
                    sentiment = "negative"
                elif sentiment.startswith("neu"):
                    sentiment = "neutral"
                else:
                    sentiment = "neutral"
        else:
            sentiment = "neutral"

        try:
            confidence = float(confidence) if confidence is not None else 0.5
        except Exception:
            confidence = 0.5

        confidence = max(0.0, min(1.0, confidence))
        logger.info("External AI sentiment result: sentiment=%s confidence=%s status=%s", sentiment, confidence, status)
        return sentiment, confidence

    except Exception as e:
        logger.warning(f"External AI sentiment failed: {e}")
        return None


# ── Public API ────────────────────────────────────────────────

async def analyze_sentiment(content: str) -> tuple[str, float]:
    """
    Phân tích sentiment. Ưu tiên external AI layer, fallback Gemini rồi rule-based.
    Trả về (sentiment, confidence).
    """
    # Ưu tiên external AI layer nếu có cấu hình, fallback về Gemini rồi rule-based
    result = await _external_ai_sentiment(content)
    if result:
        return result

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
