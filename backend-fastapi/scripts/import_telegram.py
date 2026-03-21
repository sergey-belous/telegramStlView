from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timezone
from typing import Any

from app.config import get_settings
from app.services.archive import extract_file_name_from_message, resolve_file_type
from app.services.couchdb import CouchDBService
from app.services.telethon_client import TelethonClientService


def extract_message_content(message: Any) -> str:
    text = getattr(message, "message", None)
    if isinstance(text, str):
        return text

    media = getattr(message, "media", None)
    if media is not None:
        return f"[MEDIA: {media.__class__.__name__}]"
    return ""


async def run(group_id: str | None, topic_id: int | None, limit: int) -> int:
    settings = get_settings()
    couchdb = CouchDBService(settings)
    telethon = TelethonClientService(settings)

    await couchdb.startup()
    try:
        resolved_group_id = (group_id or settings.telegram_group_id).strip()
        if resolved_group_id == "":
            raise RuntimeError("Telegram group id is required (arg --group-id or TELEGRAM_GROUP_ID).")

        resolved_topic_id = topic_id if topic_id is not None else settings.telegram_topic_id
        group_name = await telethon.get_group_title(resolved_group_id)

        imported = 0
        async for message in telethon.iter_messages(
            group_id=resolved_group_id,
            topic_id=resolved_topic_id,
            limit=limit,
        ):
            message_id = getattr(message, "id", None)
            message_date = getattr(message, "date", None)
            if message_id is None or message_date is None:
                continue

            if isinstance(message_date, datetime):
                ts = int(message_date.timestamp())
            else:
                ts = int(datetime.now(timezone.utc).timestamp())

            sender = await telethon.get_sender_info(message)
            file_name = extract_file_name_from_message(message)
            file_type = resolve_file_type(file_name)
            doc: dict[str, Any] = {
                "_id": f"tg_{resolved_group_id}_{message_id}",
                "source": "telegram",
                "group_id": resolved_group_id,
                "group_name": group_name,
                "topic_id": resolved_topic_id,
                "message_id": message_id,
                "date": datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
                "timestamp": ts,
                "content": extract_message_content(message),
                "sender": sender,
                "raw": telethon.message_to_raw(message),
            }
            if file_name:
                doc["file_name"] = file_name
                doc["file_type"] = file_type
            await couchdb.upsert_document(doc)
            imported += 1

            if imported % 100 == 0:
                print(f"Processed {imported} messages...")

        print(
            "Import completed.",
            f"group_id={resolved_group_id}",
            f"topic_id={resolved_topic_id}",
            f"imported={imported}",
        )
        return imported
    finally:
        await telethon.shutdown()
        await couchdb.shutdown()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import Telegram messages into CouchDB.")
    parser.add_argument("--group-id", dest="group_id", type=str, default=None, help="Telegram group/channel id or username")
    parser.add_argument("--topic-id", dest="topic_id", type=int, default=None, help="Telegram topic id")
    parser.add_argument("--limit", dest="limit", type=int, default=1000, help="Max messages to import")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    asyncio.run(run(args.group_id, args.topic_id, max(1, args.limit)))
