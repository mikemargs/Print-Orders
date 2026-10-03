from __future__ import annotations

import os
from urllib.parse import quote

import httpx

from .base import StoredObject, UploadAuthorization


class SupabaseStorageAdapter:
    def __init__(self, url: str | None = None, service_key: str | None = None, publishable_key: str | None = None, bucket: str | None = None):
        self.url = (url or os.environ.get("SUPABASE_URL", "")).rstrip("/")
        self.service_key = service_key or os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
        self.publishable_key = publishable_key or os.environ.get("SUPABASE_PUBLISHABLE_KEY", "")
        self.bucket = bucket or os.environ.get("SUPABASE_STORAGE_BUCKET", "print-artwork")
        if not self.url or not self.service_key or not self.publishable_key:
            raise RuntimeError("Supabase storage configuration is incomplete")

    @property
    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.service_key}", "apikey": self.service_key}

    def _storage_host(self) -> str:
        if self.url.endswith(".supabase.co"):
            return self.url.replace(".supabase.co", ".storage.supabase.co")
        return self.url

    def create_upload_authorization(self, object_key: str, mime_type: str, size_bytes: int) -> UploadAuthorization:
        path = quote(object_key, safe="/")
        response = httpx.post(
            f"{self.url}/storage/v1/object/upload/sign/{quote(self.bucket, safe='')}/{path}",
            headers={**self._headers, "Content-Type": "application/json"},
            json={},
            timeout=15,
        )
        response.raise_for_status()
        token = response.json().get("token")
        if not token:
            raise RuntimeError("Supabase did not return a signed upload token")
        return UploadAuthorization(
            object_key=object_key,
            tus_endpoint=f"{self._storage_host()}/storage/v1/upload/resumable/sign",
            token=token,
            bucket=self.bucket,
            publishable_key=self.publishable_key,
        )

    def verify_uploaded_object(self, object_key: str, expected_size: int) -> StoredObject:
        path = quote(object_key, safe="/")
        response = httpx.get(
            f"{self.url}/storage/v1/object/authenticated/{quote(self.bucket, safe='')}/{path}",
            headers={**self._headers, "Range": "bytes=0-0"},
            timeout=15,
        )
        response.raise_for_status()
        content_range = response.headers.get("content-range", "")
        size = expected_size
        if "/" in content_range:
            try:
                size = int(content_range.rsplit("/", 1)[1])
            except ValueError:
                pass
        elif response.headers.get("content-length"):
            size = int(response.headers["content-length"])
        if size != expected_size:
            raise ValueError(f"Uploaded object size mismatch: expected {expected_size}, got {size}")
        return StoredObject(object_key=object_key, size_bytes=size, mime_type=response.headers.get("content-type", "application/octet-stream"))

    def create_download_url(self, object_key: str, expires_seconds: int = 300) -> str:
        path = quote(object_key, safe="/")
        response = httpx.post(
            f"{self.url}/storage/v1/object/sign/{quote(self.bucket, safe='')}/{path}",
            headers={**self._headers, "Content-Type": "application/json"},
            json={"expiresIn": int(expires_seconds)},
            timeout=15,
        )
        response.raise_for_status()
        signed = response.json().get("signedURL") or response.json().get("signedUrl")
        if not signed:
            raise RuntimeError("Supabase did not return a signed download URL")
        return signed if signed.startswith("http") else f"{self.url}/storage/v1{signed}"

    def delete_object(self, object_key: str) -> None:
        response = httpx.delete(
            f"{self.url}/storage/v1/object/{quote(self.bucket, safe='')}",
            headers={**self._headers, "Content-Type": "application/json"},
            json={"prefixes": [object_key]},
            timeout=15,
        )
        response.raise_for_status()
