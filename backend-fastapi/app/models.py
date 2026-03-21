from __future__ import annotations

from pydantic import BaseModel, ConfigDict, model_validator


class DownloadRequest(BaseModel):
    id: int
    _id: str

    model_config = ConfigDict(extra="allow")


class UnzipRequest(BaseModel):
    _id: str | None = None
    savedUrl: str | None = None

    model_config = ConfigDict(extra="allow")

    @model_validator(mode="after")
    def validate_has_locator(self) -> "UnzipRequest":
        if not self._id and not self.savedUrl:
            raise ValueError("Either _id or savedUrl is required.")
        return self


class FileDownloadRequest(BaseModel):
    filePath: str


class ImportRequest(BaseModel):
    group_id: str | None = None
    topic_id: int | None = None
    limit: int = 1000

    model_config = ConfigDict(extra="allow")


class ImportResponse(BaseModel):
    imported: int
    group_id: str
    topic_id: int | None = None
