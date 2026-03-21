from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _get_env(name: str, default: str = "") -> str:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip()


def _get_env_int(name: str, default: int | None = None) -> int | None:
    value = _get_env(name, "")
    if value == "":
        return default
    return int(value)


def _get_env_float(name: str, default: float) -> float:
    value = _get_env(name, "")
    if value == "":
        return default
    return float(value)


def _parse_cors_origins(raw: str) -> list[str]:
    if raw.strip() == "":
        return ["*"]
    return [entry.strip() for entry in raw.split(",") if entry.strip()]


@dataclass(frozen=True)
class Settings:
    app_name: str
    cors_origins: list[str]
    public_root: str
    telegram_download_root: str
    telegram_session_path: str
    telegram_api_id: int | None
    telegram_api_hash: str
    telegram_group_id: str
    telegram_topic_id: int | None
    telegram_download_timeout_seconds: float
    telegram_lock_stale_seconds: float
    telegram_lock_wait_seconds: float
    couchdb_url: str
    couchdb_user: str
    couchdb_password: str
    couchdb_db_name: str

    @property
    def public_root_path(self) -> Path:
        return Path(self.public_root).resolve()

    @property
    def download_root_path(self) -> Path:
        return Path(self.telegram_download_root).resolve()

    @property
    def session_path(self) -> Path:
        return Path(self.telegram_session_path).resolve()


def get_settings() -> Settings:
    public_root = _get_env("PUBLIC_ROOT", "/app/public")
    default_download_root = f"{public_root.rstrip('/')}/telegram_downloads"
    return Settings(
        app_name=_get_env("APP_NAME", "telegram-stl-fastapi"),
        cors_origins=_parse_cors_origins(_get_env("CORS_ORIGINS", "*")),
        public_root=public_root,
        telegram_download_root=_get_env("TELEGRAM_DOWNLOAD_ROOT", default_download_root),
        telegram_session_path=_get_env("TELEGRAM_SESSION_PATH", "/app/session/telethon"),
        telegram_api_id=_get_env_int("TELEGRAM_API_ID", None),
        telegram_api_hash=_get_env("TELEGRAM_API_HASH", ""),
        telegram_group_id=_get_env("TELEGRAM_GROUP_ID", ""),
        telegram_topic_id=_get_env_int("TELEGRAM_TOPIC_ID", None),
        telegram_download_timeout_seconds=_get_env_float("TELEGRAM_DOWNLOAD_TIMEOUT_SECONDS", 60.0),
        telegram_lock_stale_seconds=_get_env_float("TELEGRAM_LOCK_STALE_SECONDS", 90.0),
        telegram_lock_wait_seconds=_get_env_float("TELEGRAM_LOCK_WAIT_SECONDS", 180.0),
        couchdb_url=_get_env("COUCHDB_URL", "http://couchdb:5984"),
        couchdb_user=_get_env("COUCHDB_USER", "admin"),
        couchdb_password=_get_env("COUCHDB_PASSWORD", "password"),
        couchdb_db_name=_get_env("COUCHDB_DB_NAME", "telegram_messages_2"),
    )
