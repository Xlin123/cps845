import asyncio
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import timedelta

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.clock import SystemClock
from app.db import SessionLocal, init_db
from app.profiles import sweep_pending_profiles
from app.routers.auth import router as auth_router
from app.routers.profiles import router as profiles_router
from app.routers.sessions import router as sessions_router

FRONTEND_DIST = "frontend_dist"
SWEEP_INTERVAL = timedelta(hours=1)


def _sweep_once() -> None:
    db = SessionLocal()
    try:
        sweep_pending_profiles(db, clock=SystemClock())
    finally:
        db.close()


async def _sweep_hourly() -> None:
    while True:
        await asyncio.sleep(SWEEP_INTERVAL.total_seconds())
        _sweep_once()


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    init_db()
    _sweep_once()
    task = asyncio.create_task(_sweep_hourly())
    try:
        yield
    finally:
        task.cancel()


app = FastAPI(title="CM club API", lifespan=lifespan)
app.include_router(auth_router)
app.include_router(profiles_router)
app.include_router(sessions_router)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


# The built frontend is copied here in the container image; the directory is
# absent in local dev, so mounting it is skipped outside the image.
if os.path.isdir(FRONTEND_DIST):
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")
