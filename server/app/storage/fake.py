from __future__ import annotations

from urllib.parse import quote

from .base import StoredObject, UploadAuthorization


class FakeStorageAdapter:
    def __init__(self):
        self.objects: dict[str, tuple[bytes, str]] = {}

    def create_upload_authorization(self, object_key: str, mime_type: str, size_bytes: int) -> UploadAuthorization:
        return UploadAuthorization(
            object_key=object_key,
            tus_endpoint="https://fake-storage/upload/resumable/sign",
            token=f"signed:{object_key}:{size_bytes}",
            bucket="print-artwork",
            publishable_key="fake-publishable-key",
        )

    def mark_uploaded(self, object_key: str, data: bytes, mime_type: str = "application/octet-stream") -> None:
        self.objects[object_key] = (bytes(data), mime_type)

    def verify_uploaded_object(self, object_key: str, expected_size: int) -> StoredObject:
        if object_key not in self.objects:
            raise FileNotFoundError(object_key)
        data, mime = self.objects[object_key]
        if len(data) != expected_size:
            raise ValueError(f"Uploaded object size mismatch: expected {expected_size}, got {len(data)}")
        return StoredObject(object_key=object_key, size_bytes=len(data), mime_type=mime)

    def create_download_url(self, object_key: str, expires_seconds: int = 300) -> str:
        if object_key not in self.objects:
            raise FileNotFoundError(object_key)
        return f"https://fake-storage/download/{quote(object_key)}?expires={int(expires_seconds)}"

    def delete_object(self, object_key: str) -> None:
        self.objects.pop(object_key, None)
