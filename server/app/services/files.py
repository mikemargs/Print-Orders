from __future__ import annotations

import os
import re
import uuid
from pathlib import PurePosixPath

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth_context import AuthContext
from ..database import ArtworkFile, WorkOrder, utcnow
from ..storage.base import StorageAdapter, UploadAuthorization
from .common import Forbidden, Invalid, NotFound

MAX_ARTWORK_BYTES = int(os.environ.get("MAX_UPLOAD_BYTES", str(250 * 1024 * 1024)))
BLOCKED_MIME_TYPES = {
    "application/x-msdownload",
    "application/x-dosexec",
    "application/x-executable",
    "application/x-sh",
}
BLOCKED_EXTENSIONS = {".exe", ".com", ".bat", ".cmd", ".msi", ".ps1", ".scr", ".vbs", ".sh", ".lnk"}


def sanitize_filename(filename: str) -> str:
    normalized = filename.replace("\\", "/")
    base = PurePosixPath(normalized).name
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", base).strip("._")
    if not safe:
        safe = "artwork"
    return safe[:255]


def serialize_attachment(row: ArtworkFile) -> dict:
    return {
        "id": row.id,
        "order_id": row.work_order_id,
        "object_key": row.object_key,
        "original_filename": row.original_filename,
        "mime_type": row.mime_type,
        "size_bytes": row.size_bytes,
        "uploaded_by": row.uploaded_by,
        "created_at": row.created_at.isoformat() if row.created_at else "",
        "checksum": row.checksum,
        "active": row.active,
        "deleted": row.deleted,
    }


def _order_for_access(db: Session, auth: AuthContext, order_id: str) -> WorkOrder:
    order = db.get(WorkOrder, order_id)
    if not order or order.company_id != auth.company_id or order.is_deleted:
        raise NotFound("Work order not found")
    if auth.role != "admin" and auth.location_id != order.location_id:
        raise Forbidden("Employee is not signed in to this store")
    return order


def authorize_upload(
    db: Session,
    storage: StorageAdapter,
    auth: AuthContext,
    order_id: str,
    filename: str,
    mime_type: str,
    size_bytes: int,
) -> tuple[ArtworkFile, UploadAuthorization]:
    _order_for_access(db, auth, order_id)
    if size_bytes <= 0 or size_bytes > MAX_ARTWORK_BYTES:
        raise Invalid(f"Artwork files must be between 1 byte and {MAX_ARTWORK_BYTES} bytes")
    normalized_mime = mime_type.strip().lower() or "application/octet-stream"
    normalized_filename = filename.replace("\\", "/")
    extension = PurePosixPath(normalized_filename).suffix.lower()
    if normalized_mime in BLOCKED_MIME_TYPES or extension in BLOCKED_EXTENSIONS:
        raise Invalid("This file type is not allowed")
    attachment_id = str(uuid.uuid4())
    safe_name = sanitize_filename(filename)
    object_key = f"{auth.company_id}/{order_id}/{attachment_id}/{safe_name}"
    row = ArtworkFile(
        id=attachment_id,
        company_id=auth.company_id,
        work_order_id=order_id,
        object_key=object_key,
        original_filename=filename,
        mime_type=normalized_mime,
        size_bytes=size_bytes,
        uploaded_by=auth.employee_id,
        created_at=utcnow(),
        checksum="",
        active=False,
        deleted=False,
    )
    db.add(row)
    db.flush()
    authorization = storage.create_upload_authorization(object_key, normalized_mime, size_bytes)
    return row, authorization


def finalize_upload(
    db: Session,
    storage: StorageAdapter,
    auth: AuthContext,
    order_id: str,
    attachment_id: str,
) -> ArtworkFile:
    _order_for_access(db, auth, order_id)
    row = db.scalar(
        select(ArtworkFile).where(
            ArtworkFile.id == attachment_id,
            ArtworkFile.company_id == auth.company_id,
            ArtworkFile.work_order_id == order_id,
        )
    )
    if not row:
        raise NotFound("Artwork attachment not found")
    if row.active and not row.deleted:
        return row
    stored = storage.verify_uploaded_object(row.object_key, row.size_bytes)
    if stored.size_bytes != row.size_bytes:
        raise Invalid("Uploaded artwork size does not match the authorization")
    row.active = True
    return row


def list_attachments(db: Session, auth: AuthContext, order_id: str) -> list[ArtworkFile]:
    _order_for_access(db, auth, order_id)
    return list(
        db.scalars(
            select(ArtworkFile)
            .where(
                ArtworkFile.company_id == auth.company_id,
                ArtworkFile.work_order_id == order_id,
                ArtworkFile.active.is_(True),
                ArtworkFile.deleted.is_(False),
            )
            .order_by(ArtworkFile.created_at.desc())
        ).all()
    )


def get_attachment(db: Session, auth: AuthContext, order_id: str, file_id: str) -> ArtworkFile:
    _order_for_access(db, auth, order_id)
    row = db.scalar(
        select(ArtworkFile).where(
            ArtworkFile.id == file_id,
            ArtworkFile.company_id == auth.company_id,
            ArtworkFile.work_order_id == order_id,
            ArtworkFile.active.is_(True),
            ArtworkFile.deleted.is_(False),
        )
    )
    if not row:
        raise NotFound("Artwork attachment not found")
    return row


def delete_attachment(
    db: Session,
    storage: StorageAdapter,
    auth: AuthContext,
    order_id: str,
    file_id: str,
) -> ArtworkFile:
    row = get_attachment(db, auth, order_id, file_id)
    storage.delete_object(row.object_key)
    row.active = False
    row.deleted = True
    return row
