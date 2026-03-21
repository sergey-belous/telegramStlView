from __future__ import annotations

import asyncio
import re
from pathlib import Path
from typing import Any, AsyncIterator, Callable

from fastapi.encoders import jsonable_encoder
from telethon import TelegramClient

from app.config import Settings


ProgressCallback = Callable[[int, int], None]


def _normalize_peer(peer: str) -> Any:
    value = peer.strip()
    if re.fullmatch(r"-?\d+", value):
        return int(value)
    return value


class TelethonClientService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client: TelegramClient | None = None
        self._lock = asyncio.Lock()

    async def startup(self) -> None:
        await self.get_client()

    async def shutdown(self) -> None:
        if self._client is None:
            return
        await self._client.disconnect()
        self._client = None

    async def get_client(self) -> TelegramClient:
        if self._client is not None and self._client.is_connected():
            return self._client

        async with self._lock:
            if self._client is not None and self._client.is_connected():
                return self._client
            if self._settings.telegram_api_id is None or self._settings.telegram_api_hash == "":
                raise RuntimeError("TELEGRAM_API_ID and TELEGRAM_API_HASH are required.")

            session_path = Path(self._settings.telegram_session_path)
            session_path.parent.mkdir(parents=True, exist_ok=True)
            client = TelegramClient(
                str(session_path),
                self._settings.telegram_api_id,
                self._settings.telegram_api_hash,
            )
            await client.connect()
            if not await client.is_user_authorized():
                raise RuntimeError(
                    "Telethon session is not authorized. Run an interactive login for this session file first."
                )
            self._client = client
            return self._client

    async def resolve_group_entity(self, group_id: str | None = None) -> Any:
        resolved_group_id = (group_id or self._settings.telegram_group_id).strip()
        if resolved_group_id == "":
            raise RuntimeError("Telegram group id is not configured.")
        client = await self.get_client()
        return await client.get_entity(_normalize_peer(resolved_group_id))

    async def get_group_title(self, group_id: str | None = None) -> str:
        entity = await self.resolve_group_entity(group_id)
        title = getattr(entity, "title", None)
        if isinstance(title, str) and title.strip():
            return title
        return str(getattr(entity, "id", group_id or self._settings.telegram_group_id))

    async def get_message(self, message_id: int, group_id: str | None = None) -> Any | None:
        entity = await self.resolve_group_entity(group_id)
        client = await self.get_client()
        message = await client.get_messages(entity, ids=message_id)
        if isinstance(message, list):
            return message[0] if message else None
        return message

    async def download_media_with_progress(
        self,
        message: Any,
        destination: Path,
        progress_callback: ProgressCallback,
        timeout_seconds: float,
    ) -> Path:
        client = await self.get_client()
        destination.parent.mkdir(parents=True, exist_ok=True)

        async def _download() -> Any:
            return await client.download_media(
                message,
                file=str(destination),
                progress_callback=progress_callback,
            )

        downloaded = await asyncio.wait_for(_download(), timeout=timeout_seconds)
        if downloaded is None:
            raise RuntimeError("Telegram download returned empty result.")

        downloaded_path = Path(str(downloaded)).resolve()
        return downloaded_path

    @staticmethod
    def is_message_from_topic(message: Any, topic_id: int) -> bool:
        message_id = getattr(message, "id", None)
        if message_id == topic_id:
            return True

        reply_to = getattr(message, "reply_to", None)
        if reply_to is None:
            return topic_id == 1

        forum_topic = bool(getattr(reply_to, "forum_topic", False))
        if not forum_topic:
            return topic_id == 1

        top_id = getattr(reply_to, "reply_to_top_id", None)
        msg_id = getattr(reply_to, "reply_to_msg_id", None)
        message_topic_id = top_id if top_id is not None else msg_id
        if message_topic_id is None:
            return topic_id == 1
        return int(message_topic_id) == int(topic_id)

    async def iter_messages(
        self,
        group_id: str | None = None,
        topic_id: int | None = None,
        limit: int = 1000,
    ) -> AsyncIterator[Any]:
        client = await self.get_client()
        entity = await self.resolve_group_entity(group_id)
        effective_limit = max(1, limit)
        async for message in client.iter_messages(entity, limit=effective_limit):
            if topic_id is not None and not self.is_message_from_topic(message, topic_id):
                continue
            yield message

    async def get_sender_info(self, message: Any) -> dict[str, Any] | None:
        sender = getattr(message, "sender", None)
        if sender is None and getattr(message, "sender_id", None) is not None:
            try:
                sender = await message.get_sender()
            except Exception:
                sender = None

        if sender is None:
            sender_id = getattr(message, "sender_id", None)
            if sender_id is None:
                return None
            return {"id": sender_id, "name": "Unknown", "username": None}

        sender_id = getattr(sender, "id", getattr(message, "sender_id", None))
        first_name = getattr(sender, "first_name", None)
        last_name = getattr(sender, "last_name", None)
        title = getattr(sender, "title", None)
        display_name = " ".join(part for part in [first_name, last_name] if isinstance(part, str) and part.strip())
        if display_name.strip() == "":
            display_name = title or "Unknown"
        return {
            "id": sender_id,
            "name": display_name,
            "username": getattr(sender, "username", None),
        }

    @staticmethod
    def message_to_raw(message: Any) -> dict[str, Any]:
        if hasattr(message, "to_dict"):
            return jsonable_encoder(message.to_dict())
        return jsonable_encoder({})
