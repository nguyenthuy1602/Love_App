from contextlib import asynccontextmanager
import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from starlette.requests import Request
from starlette.middleware.sessions import SessionMiddleware

from app.core.config import settings
from app.db.mongodb import connect_db, close_db
from app.db.indexes import create_indexes
from app.router.auth import router as auth_router
from app.router.posts import router as posts_router
from app.router.profile import router as profile_router
from app.router.match import router as match_router
from app.router.chat import router as chat_router
from app.router.reactions import router as reactions_router
from app.router.comments import router as comments_router
from app.router.moderation import router as moderation_router
from app.middleware.rate_limit import RateLimitMiddleware

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_db()
    await create_indexes()
    yield
    await close_db()


app = FastAPI(
    title="Love API",
    description="Backend for the Love social network",
    version="0.2.0",
    lifespan=lifespan,
)

uploads_dir = Path(__file__).resolve().parents[1] / "uploads"
uploads_dir.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(uploads_dir)), name="static")

# ── Middleware ────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "https://love-app-fe.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    SessionMiddleware,
    secret_key=settings.session_secret,
    session_cookie="love_session",
    max_age=86400,
    https_only=False,
    same_site="lax",
)

app.add_middleware(RateLimitMiddleware)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    body_preview = "<unavailable>"
    try:
        raw = await request.body()
        body_preview = raw.decode("utf-8", errors="replace")[:2000]
    except Exception:
        pass

    logger.warning(
        "422 validation error on %s %s | errors=%s | body=%s",
        request.method,
        request.url.path,
        exc.errors(),
        body_preview,
    )
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors()},
    )

# ── Routers ───────────────────────────────────────────────────

app.include_router(auth_router,       prefix="/api")
app.include_router(posts_router,      prefix="/api")
app.include_router(profile_router,    prefix="/api")
app.include_router(match_router,      prefix="/api")
app.include_router(reactions_router,  prefix="/api")
app.include_router(comments_router,   prefix="/api")
app.include_router(moderation_router, prefix="/api")

# Chat router: WebSocket path stays at /chat/ws/{match_id}
app.include_router(chat_router)


# ── Health check ──────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "env": settings.app_env}
