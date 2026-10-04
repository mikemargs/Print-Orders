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
        headers = {"apikey": self.service_key}
        # Modern sb_secret_* keys are opaque API keys, not JWTs. Sending them as
        # Authorization: Bearer makes Supabase try to parse them as JWTs.
        # Keep Bearer auth only for legacy JWT-based service_role keys.
        if not self.service_key.startswith("sb_secret_"):
            headers["Authorization"] = f"Bearer {self.service_key}"
        return headers

    @staticmethod
    def _check_response(response: httpx.Response, operation: str) -> None:
        if response.is_success:
            return
        detail = ""
        try:
            payload = response.json()
            if isinstance(payload, dict):
                detail = str(
                    payload.get("message")
                    or payload.get("error")
                    or payload.get("error_description")
                    or payload
                )
            else:
                detail = str(payload)
        except (ValueError, TypeError):
            detail = response.text.strip()
        detail = " ".join(detail.split())[:800] or "No response body"
        raise RuntimeError(
            f"Supabase Storage {operation} failed with HTTP "
            f"{response.status_code}: {detail}"
        )

    def _storage_host(self) -> str:
        if self.url.endswith(".supabase.co"):
            return self.url.replace(".supabase.co", ".storage.supabase.co")
        return self.url

    def create_upload_authorization(self, object_key: str, mime_type: str, size_bytes: int) -> UploadAuthorization:
        path = quote(object_key, safe="/")
        response = httpx.post(
            f"{self.url}/storage/v1/object/upload/sign/{quote(self.bucket, safe='')}/{path}",
            headers={**self._headers, "Content-Type": "application/json", "Accept": "application/json"},
            json={},
            timeout=15,
        )
        self._check_response(response, "signed upload authorization")
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
        self._check_response(response, "object verification")
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
            headers={**self._headers, "Content-Type": "application/json", "Accept": "application/json"},
            json={"expiresIn": int(expires_seconds)},
            timeout=15,
        )
        self._check_response(response, "signed download")
        signed = response.json().get("signedURL") or response.json().get("signedUrl")
        if not signed:
            raise RuntimeError("Supabase did not return a signed download URL")
        return signed if signed.startswith("http") else f"{self.url}/storage/v1{signed}"

    def delete_object(self, object_key: str) -> None:
        response = httpx.delete(
            f"{self.url}/storage/v1/object/{quote(self.bucket, safe='')}",
            headers={**self._headers, "Content-Type": "application/json", "Accept": "application/json"},
            json={"prefixes": [object_key]},
            timeout=15,
        )
        self._check_response(response, "object deletion")
