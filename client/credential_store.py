from __future__ import annotations

import ctypes
import os
from ctypes import wintypes
from pathlib import Path

from local_store import app_data_dir

TARGET_NAME = "PrintOrderManagerMultiStore/company_token"
CRED_TYPE_GENERIC = 1
CRED_PERSIST_LOCAL_MACHINE = 2


def _fallback_path() -> Path:
    return app_data_dir() / "company_token.dev"


def _windows_write(token: str) -> None:
    class CREDENTIALW(ctypes.Structure):
        _fields_ = [
            ("Flags", wintypes.DWORD),
            ("Type", wintypes.DWORD),
            ("TargetName", wintypes.LPWSTR),
            ("Comment", wintypes.LPWSTR),
            ("LastWritten", wintypes.FILETIME),
            ("CredentialBlobSize", wintypes.DWORD),
            ("CredentialBlob", ctypes.POINTER(ctypes.c_ubyte)),
            ("Persist", wintypes.DWORD),
            ("AttributeCount", wintypes.DWORD),
            ("Attributes", wintypes.LPVOID),
            ("TargetAlias", wintypes.LPWSTR),
            ("UserName", wintypes.LPWSTR),
        ]

    data = token.encode("utf-16-le")
    blob = (ctypes.c_ubyte * len(data)).from_buffer_copy(data)
    cred = CREDENTIALW()
    cred.Type = CRED_TYPE_GENERIC
    cred.TargetName = TARGET_NAME
    cred.CredentialBlobSize = len(data)
    cred.CredentialBlob = ctypes.cast(blob, ctypes.POINTER(ctypes.c_ubyte))
    cred.Persist = CRED_PERSIST_LOCAL_MACHINE
    cred.UserName = "PrintOrderManager"
    if not ctypes.windll.advapi32.CredWriteW(ctypes.byref(cred), 0):
        raise OSError(ctypes.get_last_error(), "Unable to save Windows credential")


def _windows_read() -> str:
    class CREDENTIALW(ctypes.Structure):
        _fields_ = [
            ("Flags", wintypes.DWORD), ("Type", wintypes.DWORD), ("TargetName", wintypes.LPWSTR),
            ("Comment", wintypes.LPWSTR), ("LastWritten", wintypes.FILETIME),
            ("CredentialBlobSize", wintypes.DWORD), ("CredentialBlob", ctypes.POINTER(ctypes.c_ubyte)),
            ("Persist", wintypes.DWORD), ("AttributeCount", wintypes.DWORD),
            ("Attributes", wintypes.LPVOID), ("TargetAlias", wintypes.LPWSTR), ("UserName", wintypes.LPWSTR),
        ]
    PCREDENTIALW = ctypes.POINTER(CREDENTIALW)
    result = PCREDENTIALW()
    if not ctypes.windll.advapi32.CredReadW(TARGET_NAME, CRED_TYPE_GENERIC, 0, ctypes.byref(result)):
        return ""
    try:
        cred = result.contents
        raw = ctypes.string_at(cred.CredentialBlob, cred.CredentialBlobSize)
        return raw.decode("utf-16-le")
    finally:
        ctypes.windll.advapi32.CredFree(result)


def _windows_delete() -> None:
    ctypes.windll.advapi32.CredDeleteW(TARGET_NAME, CRED_TYPE_GENERIC, 0)


def save_company_token(token: str) -> None:
    if not token:
        delete_company_token()
        return
    if os.name == "nt":
        _windows_write(token)
        return
    # Development/test fallback only. Production desktop builds target Windows and
    # therefore use Credential Manager instead of this file.
    path = _fallback_path()
    path.write_text(token, encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        pass


def load_company_token() -> str:
    if os.name == "nt":
        return _windows_read()
    try:
        return _fallback_path().read_text(encoding="utf-8").strip()
    except (FileNotFoundError, OSError):
        return ""


def delete_company_token() -> None:
    if os.name == "nt":
        _windows_delete()
        return
    try:
        _fallback_path().unlink()
    except FileNotFoundError:
        pass
