from __future__ import annotations

from copy import deepcopy
from typing import Any
from urllib.parse import quote

import httpx

from app.config import Settings


class CouchDBError(RuntimeError):
    pass


def merge_dicts(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(base)
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = merge_dicts(result[key], value)
        else:
            result[key] = value
    return result


class CouchDBService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client: httpx.AsyncClient | None = None

    @property
    def db_name(self) -> str:
        return self._settings.couchdb_db_name

    async def startup(self) -> None:
        if self._client is not None:
            return
        self._client = httpx.AsyncClient(
            base_url=self._settings.couchdb_url.rstrip("/"),
            auth=(self._settings.couchdb_user, self._settings.couchdb_password),
            timeout=httpx.Timeout(30.0),
        )
        await self.ensure_database()

    async def shutdown(self) -> None:
        if self._client is None:
            return
        await self._client.aclose()
        self._client = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            raise CouchDBError("CouchDB client is not initialized.")
        return self._client

    async def ensure_database(self) -> None:
        response = await self.client.put(f"/{self.db_name}")
        if response.status_code not in {201, 202, 412}:
            raise CouchDBError(f"Unable to create/verify database {self.db_name}: {response.text}")

    async def get_document(self, doc_id: str) -> dict[str, Any] | None:
        response = await self.client.get(f"/{self.db_name}/{quote(doc_id, safe='')}")
        if response.status_code == 404:
            return None
        if response.status_code >= 400:
            raise CouchDBError(f"Unable to fetch document {doc_id}: {response.text}")
        payload = response.json()
        if not isinstance(payload, dict):
            raise CouchDBError("Invalid CouchDB document payload.")
        return payload

    async def put_document(self, doc: dict[str, Any]) -> None:
        doc_id = doc.get("_id")
        if not isinstance(doc_id, str) or doc_id == "":
            raise CouchDBError("Document _id is required.")
        response = await self.client.put(
            f"/{self.db_name}/{quote(doc_id, safe='')}",
            json=doc,
        )
        if response.status_code >= 400:
            raise CouchDBError(f"Unable to upsert document {doc_id}: {response.text}")

    async def upsert_document(self, doc: dict[str, Any]) -> dict[str, Any]:
        doc_id = doc.get("_id")
        if not isinstance(doc_id, str) or doc_id == "":
            raise CouchDBError("Document _id is required for upsert.")

        existing = await self.get_document(doc_id)
        merged = merge_dicts(existing or {}, doc)
        merged["_id"] = doc_id
        if existing and "_rev" in existing:
            merged["_rev"] = existing["_rev"]

        await self.put_document(merged)
        return merged

    async def find_document_by_saved_url(self, saved_url: str) -> dict[str, Any] | None:
        response = await self.client.post(
            f"/{self.db_name}/_find",
            json={
                "selector": {"savedUrl": saved_url},
                "limit": 1,
            },
        )
        if response.status_code >= 400:
            raise CouchDBError(f"Unable to search by savedUrl: {response.text}")
        payload = response.json()
        docs = payload.get("docs", []) if isinstance(payload, dict) else []
        if not docs:
            return None
        first = docs[0]
        return first if isinstance(first, dict) else None

    async def list_documents(self, limit: int | None = None) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"include_docs": "true"}
        if isinstance(limit, int) and limit > 0:
            params["limit"] = str(limit)
        response = await self.client.get(f"/{self.db_name}/_all_docs", params=params)
        if response.status_code >= 400:
            raise CouchDBError(f"Unable to list documents: {response.text}")
        payload = response.json()
        rows = payload.get("rows", []) if isinstance(payload, dict) else []
        docs: list[dict[str, Any]] = []
        for row in rows:
            if isinstance(row, dict) and isinstance(row.get("doc"), dict):
                docs.append(row["doc"])
        return docs
