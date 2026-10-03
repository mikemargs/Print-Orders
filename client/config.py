from __future__ import annotations

import json
from pathlib import Path

from credential_store import load_company_token, save_company_token
from local_store import app_data_dir

DEFAULTS = {
    "server_url": "http://localhost:8000",
    "company_code": "UPS-PRINT",
    "company_name": "",
    "location_id": "",
    "location_name": "",
    "store_number": "",
}


def config_path() -> Path:
    return app_data_dir() / "client_config.json"


def load_config() -> dict:
    result = dict(DEFAULTS)
    stored: dict = {}
    path = config_path()
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(loaded, dict):
            stored = loaded
    except (FileNotFoundError, ValueError, OSError):
        pass

    legacy_token = str(stored.pop("company_token", "") or "")
    secure_token = load_company_token()
    if not secure_token and legacy_token:
        save_company_token(legacy_token)
        secure_token = legacy_token

    result.update(stored)
    result["company_token"] = secure_token

    # Older releases stored the bearer token in JSON. Scrub that key as soon as
    # it is encountered so an in-place upgrade does not leave a plaintext copy.
    if legacy_token:
        try:
            path.write_text(json.dumps({**DEFAULTS, **stored}, indent=2), encoding="utf-8")
        except OSError:
            pass
    return result


def save_config(values: dict) -> None:
    values = dict(values)
    if "company_token" in values:
        save_company_token(values.pop("company_token") or "")
    path = config_path()
    path.write_text(json.dumps({**DEFAULTS, **values}, indent=2), encoding="utf-8")
