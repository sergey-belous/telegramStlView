from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.telegram import router as telegram_router
from app.config import get_settings
from app.services.archive import ensure_directory_exists
from app.services.couchdb import CouchDBService
from app.services.telethon_client import TelethonClientService

settings = get_settings()
couchdb_service = CouchDBService(settings)
telethon_service = TelethonClientService(settings)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.settings = settings
    app.state.couchdb = couchdb_service
    app.state.telethon = telethon_service

    ensure_directory_exists(settings.public_root_path)
    ensure_directory_exists(settings.download_root_path)
    ensure_directory_exists(settings.session_path.parent)
    await couchdb_service.startup()
    try:
        yield
    finally:
        await telethon_service.shutdown()
        await couchdb_service.shutdown()


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(telegram_router)
