from __future__ import annotations

import json
from pathlib import Path

from local_store import app_data_dir

DEFAULTS = {
    "server_url": "http://localhost:8000",
    "company_code": "UPS-PRINT",
    "company_name": "",
    "company_token": "",
    "location_id": "",
    "location_name": "",
    "store_number": "",
}


def config_path() -> Path:
    return app_data_dir() / "client_config.json"


def load_config() -> dict:
    result = dict(DEFAULTS)
    try:
        result.update(json.loads(config_path().read_text(encoding="utf-8")))
    except (FileNotFoundError, ValueError, OSError):
        pass
    return result


def save_config(values: dict) -> None:
    path = config_path()
    path.write_text(json.dumps({**DEFAULTS, **values}, indent=2), encoding="utf-8")
