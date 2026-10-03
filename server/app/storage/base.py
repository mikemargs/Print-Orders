from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class UploadAuthorization:
    object_key: str
    tus_endpoint: str
    token: str
    bucket: str
    publishable_key: str
    chunk_size: int = 6 * 1024 * 1024


@dataclass(frozen=True)
class StoredObject:
    object_key: str
    size_bytes: int
    mime_type: str = "application/octet-stream"


class StorageAdapter(Protocol):
    def create_upload_authorization(self, object_key: str, mime_type: str, size_bytes: int) -> UploadAuthorization: ...
    def verify_uploaded_object(self, object_key: str, expected_size: int) -> StoredObject: ...
    def create_download_url(self, object_key: str, expires_seconds: int = 300) -> str: ...
    def delete_object(self, object_key: str) -> None: ...
