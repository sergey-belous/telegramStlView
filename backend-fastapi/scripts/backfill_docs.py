from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from app.config import get_settings
from app.services.archive import resolve_file_type, update_processing_state
from app.services.couchdb import CouchDBService


def _extract_file_name_from_raw(raw: Any) -> str | None:
    if not isinstance(raw, dict):
        return None
    media = raw.get("media")
    if not isinstance(media, dict):
        return None
    document = media.get("document")
    if not isinstance(document, dict):
        return None
    attributes = document.get("attributes")
    if not isinstance(attributes, list) or not attributes:
        return None
    first = attributes[0]
    if not isinstance(first, dict):
        return None
    value = first.get("file_name")
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _resolve_file_name(doc: dict[str, Any]) -> str | None:
    from_doc = doc.get("file_name")
    if isinstance(from_doc, str) and from_doc.strip():
        return from_doc.strip()
    from_raw = _extract_file_name_from_raw(doc.get("raw"))
    if from_raw:
        return from_raw
    from_saved_url = doc.get("savedUrl")
    if isinstance(from_saved_url, str) and from_saved_url.strip():
        return Path(from_saved_url).name
    return None


async def main() -> None:
    settings = get_settings()
    couchdb = CouchDBService(settings)
    await couchdb.startup()

    try:
        docs = await couchdb.list_documents()
        updated = 0

        for doc in docs:
            if not isinstance(doc, dict):
                continue
            if not isinstance(doc.get("_id"), str) or doc["_id"].strip() == "":
                continue

            patch: dict[str, Any] = {"_id": doc["_id"]}
            changed = False

            file_name = _resolve_file_name(doc)
            if file_name and doc.get("file_name") != file_name:
                patch["file_name"] = file_name
                changed = True

            file_type = resolve_file_type(file_name)
            if file_type != "other" and doc.get("file_type") != file_type:
                patch["file_type"] = file_type
                changed = True

            saved_url = doc.get("savedUrl")
            if isinstance(saved_url, str) and saved_url.strip():
                if doc.get("uploaded") is not True:
                    patch["uploaded"] = True
                    changed = True
                if file_type == "stl" and doc.get("archive_extracted") is not True:
                    patch["archive_extracted"] = True
                    changed = True
                if file_type == "zip" and "archive_extracted" not in doc:
                    patch["archive_extracted"] = False
                    changed = True

            if patch.get("uploaded") is True and file_type in {"stl", "zip"}:
                update_processing_state(patch, "download", "done", 100)
                changed = True

            if file_type == "zip":
                extracted = bool(patch.get("archive_extracted", doc.get("archive_extracted", False)))
                update_processing_state(patch, "unzip", "done" if extracted else "idle", 100 if extracted else 0)
                changed = True

            if changed:
                await couchdb.upsert_document(patch)
                updated += 1

        print(f"Backfill complete. Updated documents: {updated}")
    finally:
        await couchdb.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
