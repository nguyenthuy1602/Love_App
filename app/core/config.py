from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings


# Load environment from .env and Love_App.env if present.
# This helps local/testing workflows when the file is named Love_App.env,
# while still allowing Render to use real service environment variables.
root = Path(__file__).resolve().parents[2]
load_dotenv(root / ".env", override=False)
load_dotenv(root / "Love_App.env", override=False)


class Settings(BaseSettings):
    # ── App ───────────────────────────────────────────────────
    app_env: str = "development"
    base_url: str = "http://localhost:8000"
    session_secret: str = "CHANGE_THIS_SECRET_IN_PRODUCTION"

    # ── MongoDB ───────────────────────────────────────────────
    mongodb_uri: str = "mongodb://localhost:27017"
    database_name: str = "love_db"

    # ── Legacy Gemini fallback ──────────────────────────────────
    # Nếu external AI layer chưa cấu hình, backend vẫn có thể dùng Gemini
    gemini_api_key: str = ""
    gemini_model: str = "gemini-1.5-flash"         # nhanh và rẻ cho sentiment
    gemini_timeout: int = 8                         # seconds

    # ── External AI layer (configurable via environment for Render) ──
    ai_sentiment_api_url: str = ""   # e.g. https://my-ai-layer.example.com/sentiment
    ai_sentiment_api_key: str = ""   # optional API key for the external AI layer
    # ── Cloudinary (media upload) ─────────────────────────────
    cloudinary_cloud_name: str = ""
    cloudinary_api_key: str = ""
    cloudinary_api_secret: str = ""

    # ── Rate limiting ─────────────────────────────────────────
    rate_limit_per_minute: int = 60                 # requests/phút/IP
    rate_limit_post_per_hour: int = 20              # bài đăng/giờ/user
    rate_limit_message_per_minute: int = 30         # tin nhắn/phút/user

    class Config:
        env_file = ".env"


settings = Settings()
