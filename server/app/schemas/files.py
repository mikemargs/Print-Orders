from __future__ import annotations

from pydantic import BaseModel, Field


class UploadAuthorizationRequest(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    mime_type: str = Field(default="application/octet-stream", min_length=1, max_length=160)
    size_bytes: int = Field(gt=0)


class FinalizeUploadRequest(BaseModel):
    attachment_id: str = Field(min_length=1, max_length=36)
