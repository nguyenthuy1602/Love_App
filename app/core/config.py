from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # ── App ───────────────────────────────────────────────────
    app_env: str = "development"
    session_secret: str = "CHANGE_THIS_SECRET_IN_PRODUCTION"

    # ── MongoDB ───────────────────────────────────────────────
    mongodb_uri: str = "mongodb://localhost:27017"
    database_name: str = "love_db"

    # ── Gemini AI ─────────────────────────────────────────────
    gemini_api_key: str = ""
    gemini_model: str = "gemini-1.5-flash"         # nhanh và rẻ cho sentiment
    gemini_timeout: int = 8                         # seconds

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
