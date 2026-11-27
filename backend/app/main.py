import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.db import init_db
from app.routers.auth import router as auth_router
from app.routers.check_ins import router as check_ins_router
from app.routers.sessions import router as sessions_router

FRONTEND_DIST = "frontend_dist"


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    init_db()
    yield


app = FastAPI(title="CM club API", lifespan=lifespan)
app.include_router(auth_router)
app.include_router(sessions_router)
app.include_router(check_ins_router)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


# The built frontend is copied here in the container image; the directory is
# absent in local dev, so mounting it is skipped outside the image.
if os.path.isdir(FRONTEND_DIST):
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")
