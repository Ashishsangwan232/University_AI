import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.routes import router
from app.core.config import settings
from app.db.init_db import init_db
from app.db.session import engine


def _configure_logging() -> None:
    """Make the [UMS] pipeline visible in the uvicorn console.

    Nothing sensitive is ever logged: no username, password, OTP, cookie,
    session token, or authorization header is read by this application.
    """
    logger = logging.getLogger("campusai.ums")
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s", "%H:%M:%S"))
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False


@asynccontextmanager
async def lifespan(app: FastAPI):
    _configure_logging()
    init_db()
    yield
    try:
        from app.ums.playwright_service import ums_playwright

        ums_playwright.stop()
    except Exception:  # noqa: BLE001
        pass
    engine.dispose()


app = FastAPI(title=settings.app_name, version=settings.app_version, lifespan=lifespan)

# No browser extension exists any more, so no chrome-extension:// origin.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin, "http://127.0.0.1:5173", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/api/health")
def health():
    db_status = "ok"
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception:  # noqa: BLE001
        db_status = "unavailable"
    return {
        "status": "ok",
        "service": settings.app_name,
        "version": app.version,
        "database": db_status,
    }
