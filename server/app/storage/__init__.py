from __future__ import annotations

import os

from .fake import FakeStorageAdapter
from .supabase import SupabaseStorageAdapter

_storage = None


def get_storage():
    global _storage
    if _storage is not None:
        return _storage
    backend = os.environ.get("STORAGE_BACKEND", "").strip().lower()
    app_env = os.environ.get("APP_ENV", "development").strip().lower()
    if not backend:
        if app_env == "production":
            raise RuntimeError("STORAGE_BACKEND must be configured in production")
        backend = "fake"
    if backend == "supabase":
        _storage = SupabaseStorageAdapter()
    elif backend == "fake":
        if app_env == "production":
            raise RuntimeError("Fake storage is not allowed in production")
        _storage = FakeStorageAdapter()
    else:
        raise RuntimeError(f"Unsupported STORAGE_BACKEND: {backend}")
    return _storage


def set_storage(storage) -> None:
    global _storage
    _storage = storage
