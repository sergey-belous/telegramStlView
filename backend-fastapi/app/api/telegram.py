from __future__ import annotations

import asyncio
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncIterator

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse

from app.config import Settings
from app.models import (
    DownloadRequest,
    FileDownloadRequest,
    ImportRequest,
    ImportResponse,
    UnzipRequest,
)
from app.services.archive import (
    acquire_lock_file,
    build_absolute_public_path,
    build_archive_child_document,
    build_deterministic_download_target_path,
    build_public_url,
    ensure_directory_exists,
    extract_file_name_from_message,
    is_download_file_complete,
    normalize_archive_entry_path,
    release_lock_file,
    resolve_file_type,
    sanitize_path_segment,
    update_processing_state,
)
from app.services.couchdb import CouchDBService
from app.services.telethon_client import TelethonClientService

router = APIRouter()


def _line(value: str) -> bytes:
    return f"{value}\n".encode("utf-8")


def _get_settings(request: Request) -> Settings:
    return request.app.state.settings  # type: ignore[attr-defined]


def _get_couchdb(request: Request) -> CouchDBService:
    return request.app.state.couchdb  # type: ignore[attr-defined]


def _get_telethon(request: Request) -> TelethonClientService:
    return request.app.state.telethon  # type: ignore[attr-defined]


def _extract_message_content(message: Any) -> str:
    text = getattr(message, "message", None)
    if isinstance(text, str):
        return text

    media = getattr(message, "media", None)
    if media is not None:
        return f"[MEDIA: {media.__class__.__name__}]"
    return ""


def _doc_file_name(doc: dict[str, Any]) -> str | None:
    file_name = doc.get("file_name")
    if isinstance(file_name, str) and file_name.strip():
        return file_name.strip()

    raw = doc.get("raw")
    if isinstance(raw, dict):
        media = raw.get("media")
        if isinstance(media, dict):
            document = media.get("document")
            if isinstance(document, dict):
                attributes = document.get("attributes")
                if isinstance(attributes, list) and attributes:
                    first = attributes[0]
                    if isinstance(first, dict):
                        raw_file_name = first.get("file_name")
                        if isinstance(raw_file_name, str) and raw_file_name.strip():
                            return raw_file_name.strip()
    saved_url = doc.get("savedUrl")
    if isinstance(saved_url, str) and saved_url.strip():
        return Path(saved_url).name
    return None


@router.get("/healthz")
async def healthcheck() -> JSONResponse:
    return JSONResponse({"status": "ok"})


@router.get("/telegram/messages")
async def list_telegram_messages(request: Request) -> JSONResponse:
    couchdb = _get_couchdb(request)
    docs = await couchdb.list_documents()
    return JSONResponse({"docs": docs})


@router.post("/telegram/import", response_model=ImportResponse)
async def import_telegram_messages(payload: ImportRequest, request: Request) -> ImportResponse:
    settings = _get_settings(request)
    couchdb = _get_couchdb(request)
    telethon = _get_telethon(request)

    group_id = (payload.group_id or settings.telegram_group_id).strip()
    if group_id == "":
        raise HTTPException(status_code=400, detail="Telegram group id is required.")

    topic_id = payload.topic_id if payload.topic_id is not None else settings.telegram_topic_id
    imported = 0
    group_name = await telethon.get_group_title(group_id)

    async for message in telethon.iter_messages(group_id=group_id, topic_id=topic_id, limit=payload.limit):
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
            "_id": f"tg_{group_id}_{message_id}",
            "source": "telegram",
            "group_id": group_id,
            "group_name": group_name,
            "topic_id": topic_id,
            "message_id": message_id,
            "date": datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
            "timestamp": ts,
            "content": _extract_message_content(message),
            "sender": sender,
            "raw": telethon.message_to_raw(message),
        }
        if file_name:
            doc["file_name"] = file_name
            doc["file_type"] = file_type
        await couchdb.upsert_document(doc)
        imported += 1

    return ImportResponse(imported=imported, group_id=group_id, topic_id=topic_id)


@router.post("/telegram/download")
async def download_telegram_item(payload: DownloadRequest, request: Request) -> StreamingResponse:
    settings = _get_settings(request)
    couchdb = _get_couchdb(request)
    telethon = _get_telethon(request)
    ensure_directory_exists(settings.download_root_path)

    async def stream() -> AsyncIterator[bytes]:
        doc_for_update: dict[str, Any] = {"_id": payload._id}
        lock_path: Path | None = None
        lock_acquired = False

        try:
            existing = await couchdb.get_document(payload._id)
            if isinstance(existing, dict):
                doc_for_update = existing
            doc_for_update["_id"] = payload._id
            update_processing_state(doc_for_update, "download", "in_progress", 0)
            await couchdb.upsert_document(doc_for_update)

            yield _line(f"Message id: {payload.id}")

            message = await telethon.get_message(payload.id)
            if message is None:
                raise RuntimeError("Message not found in Telegram history.")
            if getattr(message, "media", None) is None:
                raise RuntimeError("Message does not contain downloadable media.")

            file_name = extract_file_name_from_message(message)
            if file_name:
                doc_for_update["file_name"] = file_name
                doc_for_update["file_type"] = resolve_file_type(file_name)
                await couchdb.upsert_document(doc_for_update)

            file_info = getattr(message, "file", None)
            expected_size = getattr(file_info, "size", None)
            if not isinstance(expected_size, int):
                expected_size = None

            target_file_path = build_deterministic_download_target_path(
                settings.download_root_path,
                file_name,
                payload.id,
            ).resolve()
            lock_path = target_file_path.with_suffix(target_file_path.suffix + ".lock")

            downloaded_path = target_file_path
            emitted_progress = -1

            if is_download_file_complete(target_file_path, expected_size):
                yield _line("Progress: 100%")
            else:
                wait_started_at = time.time()
                stagnant_ticks = 0
                last_size = -1
                while lock_path.exists():
                    if is_download_file_complete(target_file_path, expected_size):
                        break

                    current_size = target_file_path.stat().st_size if target_file_path.exists() else 0
                    if current_size != last_size:
                        last_size = current_size
                        stagnant_ticks = 0
                    else:
                        stagnant_ticks += 1

                    current_progress = 1
                    if isinstance(expected_size, int) and expected_size > 0:
                        current_progress = max(1, min(98, int(round((current_size / expected_size) * 100))))
                    if current_progress != emitted_progress:
                        emitted_progress = current_progress
                        yield _line(f"Progress: {current_progress}%")

                    lock_age = time.time() - lock_path.stat().st_mtime
                    waited = time.time() - wait_started_at
                    if (
                        lock_age > settings.telegram_lock_stale_seconds
                        or stagnant_ticks >= 30
                        or waited > settings.telegram_lock_wait_seconds
                    ):
                        release_lock_file(lock_path)
                        break
                    await asyncio.sleep(1)

                if not is_download_file_complete(target_file_path, expected_size):
                    if acquire_lock_file(lock_path):
                        lock_acquired = True
                    else:
                        retry_started_at = time.time()
                        while not lock_acquired and time.time() - retry_started_at < settings.telegram_lock_wait_seconds:
                            if is_download_file_complete(target_file_path, expected_size):
                                break
                            if acquire_lock_file(lock_path):
                                lock_acquired = True
                                break
                            await asyncio.sleep(1)
                        if not lock_acquired and not is_download_file_complete(target_file_path, expected_size):
                            raise RuntimeError("Download is busy, please retry.")

                if not is_download_file_complete(target_file_path, expected_size):
                    queue: asyncio.Queue[int] = asyncio.Queue()
                    download_error: Exception | None = None
                    downloaded_result: Path | None = None
                    progress_last = emitted_progress

                    def on_progress(current: int, total: int) -> None:
                        if total <= 0:
                            return
                        progress = max(1, min(100, int(round((current / total) * 100))))
                        queue.put_nowait(progress)

                    async def run_download() -> None:
                        nonlocal download_error, downloaded_result
                        try:
                            downloaded_result = await telethon.download_media_with_progress(
                                message=message,
                                destination=target_file_path,
                                progress_callback=on_progress,
                                timeout_seconds=settings.telegram_download_timeout_seconds,
                            )
                        except Exception as exc:
                            download_error = exc

                    download_task = asyncio.create_task(run_download())
                    while not download_task.done() or not queue.empty():
                        try:
                            progress = await asyncio.wait_for(queue.get(), timeout=0.25)
                            if progress != progress_last:
                                progress_last = progress
                                emitted_progress = progress
                                yield _line(f"Progress: {progress}%")
                        except asyncio.TimeoutError:
                            continue

                    await download_task
                    if download_error:
                        if isinstance(download_error, asyncio.TimeoutError):
                            raise RuntimeError("Telegram file download timed out.")
                        raise download_error

                    if downloaded_result is None:
                        raise RuntimeError("Failed to download media file.")
                    downloaded_path = downloaded_result.resolve()

            if not downloaded_path.is_file():
                raise RuntimeError("Failed to download media file.")

            resolved_file_name = str(doc_for_update.get("file_name") or downloaded_path.name)
            resolved_file_type = resolve_file_type(resolved_file_name)
            saved_url = build_public_url(downloaded_path, settings.public_root_path)

            doc_for_update["uploaded"] = True
            doc_for_update["savedUrl"] = saved_url
            doc_for_update["file_name"] = resolved_file_name
            doc_for_update["file_type"] = resolved_file_type
            if resolved_file_type == "zip":
                archive_extracted = bool(doc_for_update.get("archive_extracted", False))
                doc_for_update["archive_extracted"] = archive_extracted
                update_processing_state(
                    doc_for_update,
                    "unzip",
                    "done" if archive_extracted else "idle",
                    100 if archive_extracted else 0,
                )
            else:
                doc_for_update["archive_extracted"] = True

            update_processing_state(doc_for_update, "download", "done", 100)
            await couchdb.upsert_document(doc_for_update)
            if emitted_progress < 100:
                yield _line("Progress: 100%")
            yield _line(f"Saved to: {downloaded_path}")
        except Exception as exc:
            message = str(exc).strip() or "Download failed."
            yield _line(f"[ERROR]{message}")
            try:
                update_processing_state(doc_for_update, "download", "failed", 0, message)
                await couchdb.upsert_document(doc_for_update)
            except Exception:
                pass
        finally:
            if lock_acquired and lock_path is not None:
                release_lock_file(lock_path)

    return StreamingResponse(
        stream(),
        media_type="text/plain; charset=utf-8",
        headers={
            "X-Accel-Buffering": "no",
            "Cache-Control": "no-store",
            "Connection": "keep-alive",
            "Content-Encoding": "identity",
        },
    )


@router.post("/telegram/unzip")
async def unzip_telegram_archive(payload: UnzipRequest, request: Request) -> StreamingResponse:
    settings = _get_settings(request)
    couchdb = _get_couchdb(request)

    parent_doc: dict[str, Any] | None = None
    if payload._id:
        parent_doc = await couchdb.get_document(payload._id)
    elif payload.savedUrl:
        parent_doc = await couchdb.find_document_by_saved_url(payload.savedUrl)

    if parent_doc is None or not isinstance(parent_doc.get("_id"), str):
        raise HTTPException(status_code=404, detail="ZIP source document not found in CouchDB.")

    saved_url = parent_doc.get("savedUrl") if isinstance(parent_doc.get("savedUrl"), str) else payload.savedUrl
    if not isinstance(saved_url, str) or saved_url.strip() == "":
        raise HTTPException(status_code=400, detail="savedUrl is missing for archive document.")

    file_name = _doc_file_name(parent_doc)
    file_type = resolve_file_type(file_name or saved_url)
    if file_type != "zip":
        raise HTTPException(status_code=400, detail="Requested file is not a ZIP archive.")

    try:
        zip_path = build_absolute_public_path(saved_url, settings.public_root_path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not zip_path.is_file():
        raise HTTPException(status_code=404, detail="ZIP archive not found on server.")

    parent_id = str(parent_doc["_id"])
    safe_doc_id = sanitize_path_segment(parent_id)
    extract_root = (settings.download_root_path / "unzipped" / safe_doc_id).resolve()
    ensure_directory_exists(extract_root)
    extract_public_path = build_public_url(extract_root, settings.public_root_path)

    async def stream() -> AsyncIterator[bytes]:
        try:
            parent_update: dict[str, Any] = {"_id": parent_id, "file_type": "zip", "archive_extracted": False}
            update_processing_state(parent_update, "unzip", "in_progress", 0)
            await couchdb.upsert_document(parent_update)

            with zipfile.ZipFile(zip_path, "r") as archive_file:
                entries = archive_file.infolist()
                total_entries = len(entries)
                stl_entries = 0

                if total_entries == 0:
                    yield _line("Progress: 100%")

                for index, entry in enumerate(entries, start=1):
                    relative_path = normalize_archive_entry_path(entry.filename)
                    if relative_path is not None:
                        target_path = (extract_root / relative_path).resolve()
                        try:
                            target_path.relative_to(extract_root)
                        except ValueError:
                            relative_path = None

                    if relative_path is not None:
                        target_path = (extract_root / relative_path).resolve()
                        ensure_directory_exists(target_path.parent)

                        if entry.is_dir():
                            ensure_directory_exists(target_path)
                        else:
                            with archive_file.open(entry, "r") as source_stream, open(target_path, "wb") as target_stream:
                                while True:
                                    chunk = source_stream.read(1024 * 1024)
                                    if not chunk:
                                        break
                                    target_stream.write(chunk)

                            if resolve_file_type(relative_path) == "stl":
                                child_saved_url = build_public_url(target_path, settings.public_root_path)
                                child_doc = build_archive_child_document(parent_doc, relative_path, child_saved_url)
                                await couchdb.upsert_document(child_doc)
                                stl_entries += 1

                    progress = int(round((index / total_entries) * 100)) if total_entries > 0 else 100
                    yield _line(f"Progress: {progress}%")

            parent_update = {
                "_id": parent_id,
                "archive_extracted": True,
                "unzip_dir": extract_public_path,
                "unzip_total_entries": total_entries,
                "unzip_stl_entries": stl_entries,
            }
            update_processing_state(parent_update, "unzip", "done", 100)
            await couchdb.upsert_document(parent_update)
            yield _line(f"Unzip done. STL files: {stl_entries}")
        except Exception as exc:
            error_message = str(exc).strip() or "Unzip failed."
            yield _line(f"[ERROR]{error_message}")
            try:
                failed_doc = {"_id": parent_id}
                update_processing_state(failed_doc, "unzip", "failed", 0, error_message)
                await couchdb.upsert_document(failed_doc)
            except Exception:
                pass

    return StreamingResponse(
        stream(),
        media_type="text/plain; charset=utf-8",
        headers={
            "X-Accel-Buffering": "no",
            "Cache-Control": "no-store",
            "Connection": "keep-alive",
            "Content-Encoding": "identity",
        },
    )


@router.post("/telegram-downloads/download")
async def download_model_from_server(payload: FileDownloadRequest, request: Request) -> FileResponse:
    settings = _get_settings(request)
    try:
        file_path = build_absolute_public_path(payload.filePath, settings.public_root_path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="File not found.")

    return FileResponse(
        path=str(file_path),
        filename=file_path.name,
        media_type="application/octet-stream",
    )
