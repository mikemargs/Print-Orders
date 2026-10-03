from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

router = APIRouter(include_in_schema=False)


def _web_dist() -> Path:
    configured = os.environ.get("WEB_DIST_DIR", "").strip()
    if configured:
        return Path(configured).expanduser().resolve()
    return (Path(__file__).resolve().parents[3] / "web" / "dist").resolve()


def _safe_file(root: Path, relative: str) -> Path | None:
    try:
        candidate = (root / relative).resolve()
        candidate.relative_to(root)
    except (ValueError, OSError):
        return None
    return candidate if candidate.is_file() else None


@router.get("/{full_path:path}")
def spa_fallback(full_path: str):
    if full_path == "api" or full_path.startswith("api/"):
        raise HTTPException(404, "Not found")

    root = _web_dist()
    direct = _safe_file(root, full_path) if full_path else None
    if direct is not None:
        return FileResponse(direct)

    index = _safe_file(root, "index.html")
    if index is None:
        raise HTTPException(404, "Web application has not been built")
    return FileResponse(index, media_type="text/html")
