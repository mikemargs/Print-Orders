from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..schemas.files import FinalizeUploadRequest, UploadAuthorizationRequest
from ..services.common import Forbidden, Invalid, NotFound
from ..services.files import (
    authorize_upload,
    delete_attachment,
    finalize_upload,
    get_attachment,
    list_attachments,
    serialize_attachment,
)
from ..storage import get_storage
from ..web_sessions import get_web_db, web_auth_context, web_mutation_context

router = APIRouter(prefix="/api/orders/{order_id}/files", tags=["files"])


def _raise_service_error(exc: Exception):
    if isinstance(exc, NotFound):
        raise HTTPException(404, str(exc)) from exc
    if isinstance(exc, Forbidden):
        raise HTTPException(403, str(exc)) from exc
    if isinstance(exc, Invalid):
        raise HTTPException(400, str(exc)) from exc
    raise exc


@router.post("/upload-authorizations", status_code=201)
def create_upload_authorization(order_id: str, body: UploadAuthorizationRequest, auth=Depends(web_mutation_context), db: Session = Depends(get_web_db)):
    storage = get_storage()
    try:
        row, authorization = authorize_upload(db, storage, auth, order_id, body.filename, body.mime_type, body.size_bytes)
        db.commit()
        return {
            "attachment": serialize_attachment(row),
            "object_key": authorization.object_key,
            "tus_endpoint": authorization.tus_endpoint,
            "token": authorization.token,
            "bucket": authorization.bucket,
            "publishable_key": authorization.publishable_key,
            "chunk_size": authorization.chunk_size,
        }
    except Exception as exc:
        db.rollback()
        return _raise_service_error(exc)


@router.post("/finalize")
def finalize(order_id: str, body: FinalizeUploadRequest, auth=Depends(web_mutation_context), db: Session = Depends(get_web_db)):
    try:
        row = finalize_upload(db, get_storage(), auth, order_id, body.attachment_id)
        db.commit()
        return serialize_attachment(row)
    except Exception as exc:
        db.rollback()
        return _raise_service_error(exc)


@router.get("")
def list_files(order_id: str, auth=Depends(web_auth_context), db: Session = Depends(get_web_db)):
    try:
        rows = list_attachments(db, auth, order_id)
        return {"files": [serialize_attachment(x) for x in rows]}
    except Exception as exc:
        return _raise_service_error(exc)


@router.get("/{file_id}/download")
def download(order_id: str, file_id: str, auth=Depends(web_auth_context), db: Session = Depends(get_web_db)):
    try:
        row = get_attachment(db, auth, order_id, file_id)
        return {"url": get_storage().create_download_url(row.object_key, 300), "expires_in": 300}
    except Exception as exc:
        return _raise_service_error(exc)


@router.delete("/{file_id}")
def remove(order_id: str, file_id: str, auth=Depends(web_mutation_context), db: Session = Depends(get_web_db)):
    try:
        row = delete_attachment(db, get_storage(), auth, order_id, file_id)
        db.commit()
        return {"deleted": True, "file": serialize_attachment(row)}
    except Exception as exc:
        db.rollback()
        return _raise_service_error(exc)
