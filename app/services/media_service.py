"""
Media Service — Cloudinary Upload
Hỗ trợ upload ảnh (≤10MB) và video (≤50MB).
Trả về URL công khai để lưu vào bài đăng hoặc avatar.
"""

import io
import hashlib
import time
import hmac
import httpx
import logging
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile, HTTPException

from app.core.config import settings

logger = logging.getLogger(__name__)
DEV_UPLOAD_ROOT = Path(__file__).resolve().parents[2] / "uploads"

# ── Constants ─────────────────────────────────────────────────

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
ALLOWED_VIDEO_TYPES = {"video/mp4", "video/webm", "video/quicktime"}
MAX_IMAGE_BYTES = 10 * 1024 * 1024   # 10 MB
MAX_VIDEO_BYTES = 50 * 1024 * 1024   # 50 MB


def _validate_file(file: UploadFile, content: bytes) -> str:
    """Kiểm tra MIME type và kích thước. Trả về 'image' hoặc 'video'."""
    content_type = file.content_type or ""

    if content_type in ALLOWED_IMAGE_TYPES:
        if len(content) > MAX_IMAGE_BYTES:
            raise HTTPException(status_code=413, detail="Image must be ≤ 10MB")
        return "image"

    if content_type in ALLOWED_VIDEO_TYPES:
        if len(content) > MAX_VIDEO_BYTES:
            raise HTTPException(status_code=413, detail="Video must be ≤ 50MB")
        return "video"

    raise HTTPException(
        status_code=415,
        detail=f"Unsupported file type: {content_type}. "
               f"Allowed: JPEG, PNG, WEBP, GIF, MP4, WEBM, MOV",
    )


def _make_signature(params: dict, api_secret: str) -> str:
    """Tạo chữ ký SHA-1 cho Cloudinary upload."""
    sorted_params = "&".join(
        f"{k}={v}" for k, v in sorted(params.items())
    )
    to_sign = sorted_params + api_secret
    return hashlib.sha1(to_sign.encode()).hexdigest()


async def upload_media(file: UploadFile, user_id: str, folder: str = "posts") -> dict:
    """
    Upload file lên Cloudinary.
    Trả về { url, media_type, public_id, width, height (nếu là ảnh) }.
    
    Nếu Cloudinary chưa cấu hình (dev), trả về mock URL.
    """
    logger.info(
        "Media upload request: user_id=%s filename=%s content_type=%s folder=%s",
        user_id,
        file.filename,
        file.content_type,
        folder,
    )

    content = await file.read()
    media_type = _validate_file(file, content)

    # Dev mode: Cloudinary chưa cấu hình
    if not settings.cloudinary_cloud_name:
        if settings.app_env.lower() in {"development", "dev", "local"}:
            logger.warning("Cloudinary not configured in %s — saving locally", settings.app_env)
            local_dir = DEV_UPLOAD_ROOT / folder / user_id
            local_dir.mkdir(parents=True, exist_ok=True)

            suffix = Path(file.filename or "upload").suffix.lower() or ".bin"
            local_name = f"{int(time.time())}_{uuid4().hex}{suffix}"
            local_path = local_dir / local_name
            local_path.write_bytes(content)

            return {
                "url": f"http://localhost:8000/static/{folder}/{user_id}/{local_name}",
                "media_type": media_type,
                "public_id": f"local/{folder}/{user_id}/{local_name}",
            }

        logger.error("Cloudinary configuration missing in non-development environment")
        raise HTTPException(status_code=503, detail="Media storage is not configured")

    # Cloudinary signed upload
    timestamp = int(time.time())
    public_id = f"{folder}/{user_id}/{timestamp}"

    sign_params = {
        "folder": folder,
        "public_id": public_id,
        "timestamp": timestamp,
    }
    if media_type == "video":
        sign_params["resource_type"] = "video"

    signature = _make_signature(sign_params, settings.cloudinary_api_secret)

    upload_url = (
        f"https://api.cloudinary.com/v1_1/{settings.cloudinary_cloud_name}"
        f"/{media_type}/upload"
    )

    form_data = {
        "api_key": settings.cloudinary_api_key,
        "timestamp": str(timestamp),
        "signature": signature,
        "folder": folder,
        "public_id": public_id,
    }

    files = {"file": (file.filename, io.BytesIO(content), file.content_type)}

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(upload_url, data=form_data, files=files)
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPStatusError as e:
        logger.error(f"Cloudinary upload error: {e.response.text}")
        raise HTTPException(status_code=502, detail="Media upload failed")
    except Exception as e:
        logger.error(f"Cloudinary upload exception: {e}")
        raise HTTPException(status_code=502, detail="Media upload failed")

    result = {
        "url": data["secure_url"],
        "media_type": media_type,
        "public_id": data["public_id"],
    }
    if media_type == "image":
        result["width"] = data.get("width")
        result["height"] = data.get("height")

    return result


async def upload_avatar(file: UploadFile, user_id: str) -> str:
    """Upload avatar — chỉ ảnh, crop vuông, trả về URL."""
    content = await file.read()

    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=415, detail="Avatar must be an image (JPEG, PNG, WEBP)")
    if len(content) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="Avatar must be ≤ 10MB")

    if not settings.cloudinary_cloud_name:
        return f"https://placeholder.love-app.dev/avatars/{user_id}.jpg"

    timestamp = int(time.time())
    public_id = f"avatars/{user_id}"

    sign_params = {
        "folder": "avatars",
        "public_id": public_id,
        "timestamp": timestamp,
        "transformation": "c_fill,g_face,h_400,w_400",
    }
    signature = _make_signature(sign_params, settings.cloudinary_api_secret)

    upload_url = (
        f"https://api.cloudinary.com/v1_1/{settings.cloudinary_cloud_name}/image/upload"
    )
    form_data = {
        "api_key": settings.cloudinary_api_key,
        "timestamp": str(timestamp),
        "signature": signature,
        "folder": "avatars",
        "public_id": public_id,
        "transformation": "c_fill,g_face,h_400,w_400",
    }
    files = {"file": (file.filename, io.BytesIO(content), file.content_type)}

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(upload_url, data=form_data, files=files)
            resp.raise_for_status()
            return resp.json()["secure_url"]
    except Exception as e:
        logger.error(f"Avatar upload failed: {e}")
        raise HTTPException(status_code=502, detail="Avatar upload failed")
