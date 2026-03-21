from __future__ import annotations

import hashlib
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_directory_exists(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def sanitize_path_segment(value: str) -> str:
    sanitized = re.sub(r"[^a-zA-Z0-9_-]", "_", value)
    if sanitized.strip("_") == "":
        return f"archive_{hashlib.sha1(value.encode('utf-8')).hexdigest()[:12]}"
    return sanitized


def resolve_file_type(file_name: str | None) -> str:
    if not file_name:
        return "other"
    extension = Path(file_name).suffix.lower()
    if extension == ".stl":
        return "stl"
    if extension == ".zip":
        return "zip"
    return "other"


def extract_file_name_from_message(message: Any) -> str | None:
    file_obj = getattr(message, "file", None)
    file_name = getattr(file_obj, "name", None)
    if isinstance(file_name, str) and file_name.strip():
        return file_name.strip()
    return None


def normalize_archive_entry_path(entry_path: str) -> str | None:
    normalized = entry_path.replace("\\", "/").lstrip("/")
    if normalized == "" or normalized.endswith("/"):
        return None

    parts: list[str] = []
    for part in normalized.split("/"):
        if part in {"", "."}:
            continue
        if part == "..":
            return None
        parts.append(part)

    if not parts:
        return None
    return "/".join(parts)


def build_public_url(absolute_path: str | Path, public_root: str | Path) -> str:
    absolute = Path(absolute_path).resolve()
    public = Path(public_root).resolve()
    relative = absolute.relative_to(public)
    return "/" + relative.as_posix().lstrip("/")


def build_absolute_public_path(file_path: str, public_root: str | Path) -> Path:
    normalized = "/" + file_path.replace("\\", "/").lstrip("/")
    if ".." in normalized:
        raise ValueError("Invalid file path.")
    if not normalized.startswith("/telegram_downloads/"):
        raise ValueError("Only files from /telegram_downloads are allowed.")

    absolute = (Path(public_root).resolve() / normalized.lstrip("/")).resolve()
    public = Path(public_root).resolve()
    absolute.relative_to(public)
    return absolute


def update_processing_state(
    doc: dict[str, Any],
    operation: str,
    status: str,
    progress: int,
    error: str | None = None,
) -> None:
    processing = doc.setdefault("processing", {})
    processing[operation] = {
        "status": status,
        "progress": max(0, min(100, int(progress))),
        "updated_at": now_iso(),
    }
    if error:
        processing[operation]["error"] = error


def build_archive_child_document(parent_doc: dict[str, Any], relative_path: str, saved_url: str) -> dict[str, Any]:
    parent_id = str(parent_doc.get("_id", "unknown"))
    ts = int(datetime.now(tz=timezone.utc).timestamp())
    now = now_iso()
    return {
        "_id": f"zip_{hashlib.sha1(f'{parent_id}|{relative_path}'.encode('utf-8')).hexdigest()}",
        "source": "telegram_zip_entry",
        "parent_doc_id": parent_id,
        "group_id": parent_doc.get("group_id"),
        "group_name": parent_doc.get("group_name"),
        "topic_id": parent_doc.get("topic_id"),
        "message_id": parent_doc.get("message_id"),
        "date": datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        "timestamp": ts,
        "content": f"[ZIP_ENTRY: {relative_path}]",
        "uploaded": True,
        "savedUrl": saved_url,
        "file_name": Path(relative_path).name,
        "file_type": "stl",
        "archive_extracted": True,
        "zip_entry_path": relative_path,
        "processing": {
            "download": {"status": "done", "progress": 100, "updated_at": now},
            "unzip": {"status": "done", "progress": 100, "updated_at": now},
        },
    }


def build_deterministic_download_target_path(download_root: Path, file_name: str | None, message_id: int) -> Path:
    resolved_name = file_name or f"{message_id}.bin"
    path_name = Path(resolved_name).name
    stem = sanitize_path_segment(Path(path_name).stem)
    suffix = Path(path_name).suffix.lower()
    if suffix == "":
        suffix = ".bin"
    return download_root / f"{message_id}_{stem}{suffix}"


def is_download_file_complete(file_path: Path, expected_size: int | None) -> bool:
    if not file_path.is_file():
        return False
    if expected_size is None or expected_size <= 0:
        return file_path.stat().st_size > 0
    return file_path.stat().st_size >= expected_size


def acquire_lock_file(lock_path: Path) -> bool:
    try:
        flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
        fd = os.open(str(lock_path), flags)
        os.write(fd, str(datetime.now(tz=timezone.utc).timestamp()).encode("utf-8"))
        os.close(fd)
        return True
    except FileExistsError:
        return False


def release_lock_file(lock_path: Path) -> None:
    try:
        lock_path.unlink(missing_ok=True)
    except Exception:
        # Stream should not fail because cleanup is best-effort.
        pass
