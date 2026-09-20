import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import Base, SessionLocal, engine
from app.retention import cleanup_expired
from app.routers import auth, nodes, ws
from app.utils import ensure_default_admin

logger = logging.getLogger("ops_platform")


async def _retention_loop() -> None:
    while True:
        try:
            db = SessionLocal()
            try:
                result = cleanup_expired(db)
                logger.info("retention cleanup %s", result)
            finally:
                db.close()
        except Exception:
            logger.exception("retention cleanup failed")
        await asyncio.sleep(3600)


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        ensure_default_admin(db)
    finally:
        db.close()
    task = asyncio.create_task(_retention_loop())
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


app = FastAPI(title="Ops Platform", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(nodes.router)
app.include_router(ws.router)


@app.get("/api/v1/health")
def health() -> dict:
    return {"ok": True, "project_deploy_enabled": settings.project_deploy_enabled}
