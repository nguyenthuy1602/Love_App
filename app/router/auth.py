from fastapi import APIRouter, HTTPException, Request, UploadFile, File

from app.db.mongodb import get_database
from app.schemas.user import (
    UserRegisterRequest, UserLoginRequest, UserUpdateRequest,
    UserResponse, LoginResponse,
)
from app.services.user_service import register_user, login_user, get_user_by_id, update_user
from app.services.media_service import upload_avatar
from app.core.deps import require_session
from app.core.connection_manager import manager

router = APIRouter(prefix="/auth", tags=["Authentication"])


def _require_session(request: Request) -> str:
    user_id = request.session.get("user_id")
    if not user_id:
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user_id


@router.post("/register", response_model=UserResponse, status_code=201)
async def register(body: UserRegisterRequest):
    db = get_database()
    try:
        return await register_user(db, body)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/login", response_model=LoginResponse)
async def login(body: UserLoginRequest, request: Request):
    db = get_database()
    try:
        user = await login_user(db, body.username, body.password)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))

    request.session["user_id"] = user.id
    request.session["username"] = user.username
    manager.mark_online(user.id)
    return LoginResponse(message="Login successful", user=user)


@router.post("/logout")
async def logout(request: Request):
    user_id = request.session.get("user_id")
    if user_id:
        manager.mark_offline(user_id)
    request.session.clear()
    return {"message": "Logged out successfully"}


@router.get("/me", response_model=UserResponse)
async def get_me(request: Request):
    user_id = _require_session(request)
    db = get_database()
    try:
        return await get_user_by_id(db, user_id, is_online=True)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.patch("/me", response_model=UserResponse)
async def update_me(body: UserUpdateRequest, request: Request):
    user_id = _require_session(request)
    db = get_database()
    try:
        return await update_user(db, user_id, bio=body.bio)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/me/avatar", response_model=UserResponse)
async def upload_my_avatar(request: Request, file: UploadFile = File(...)):
    """Upload ảnh đại diện. Tự động crop vuông 400x400 qua Cloudinary."""
    user_id = _require_session(request)
    db = get_database()

    avatar_url = await upload_avatar(file, user_id)
    try:
        return await update_user(db, user_id, avatar_url=avatar_url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
