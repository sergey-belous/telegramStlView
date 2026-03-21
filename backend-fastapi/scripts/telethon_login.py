from __future__ import annotations

import asyncio
import os
from pathlib import Path

from telethon import TelegramClient


def get_env(name: str, default: str = "") -> str:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip()


async def main() -> None:
    api_id_raw = get_env("TELEGRAM_API_ID", "")
    api_hash = get_env("TELEGRAM_API_HASH", "")
    session_path_raw = get_env("TELEGRAM_SESSION_PATH", "/app/session/telethon")

    if api_id_raw == "" or api_hash == "":
        raise RuntimeError("Set TELEGRAM_API_ID and TELEGRAM_API_HASH before running this script.")

    api_id = int(api_id_raw)
    session_path = Path(session_path_raw)
    session_path.parent.mkdir(parents=True, exist_ok=True)

    client = TelegramClient(str(session_path), api_id, api_hash)
    await client.start()
    me = await client.get_me()
    if me is None:
        raise RuntimeError("Unable to complete Telethon login.")

    print(f"Telethon session initialized: {session_path}")
    print(f"Authorized as user id={getattr(me, 'id', 'unknown')}")
    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
