from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from datetime import UTC, datetime, timedelta

import jwt

ITERATIONS = 310_000
JWT_ALGORITHM = "HS256"


def hash_secret(secret: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", secret.encode("utf-8"), salt, ITERATIONS)
    return f"pbkdf2_sha256${ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_secret(secret: str, encoded: str) -> bool:
    try:
        algorithm, iterations, salt_hex, digest_hex = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        actual = hashlib.pbkdf2_hmac(
            "sha256", secret.encode("utf-8"), bytes.fromhex(salt_hex), int(iterations)
        )
        return hmac.compare_digest(actual, bytes.fromhex(digest_hex))
    except (ValueError, TypeError):
        return False


def jwt_secret() -> str:
    value = os.environ.get("JWT_SECRET", "")
    if len(value) < 32:
        raise RuntimeError("JWT_SECRET must be set to a random value of at least 32 characters")
    return value


def make_token(
    company_id: str,
    token_type: str,
    employee_id: str = "",
    role: str = "",
    lifetime: timedelta | None = None,
    location_id: str = "",
    auth_version: int = 0,
    extra_claims: dict | None = None,
) -> str:
    now = datetime.now(UTC)
    lifetime = lifetime or (timedelta(days=365) if token_type == "company" else timedelta(hours=16))
    claims = {
        "company_id": company_id,
        "type": token_type,
        "employee_id": employee_id,
        "role": role,
        "location_id": location_id,
        "auth_version": auth_version,
        "iat": now,
        "exp": now + lifetime,
    }
    if extra_claims:
        claims.update(extra_claims)
    return jwt.encode(claims, jwt_secret(), algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    return jwt.decode(token, jwt_secret(), algorithms=[JWT_ALGORITHM])

# Lightweight process-local protection against rapid credential guessing. Production
# deployments should also use provider/edge rate limits because this state is per worker.
import threading
import time
from collections import defaultdict

_login_lock = threading.Lock()
_login_failures: dict[str, list[float]] = defaultdict(list)


def _login_limits() -> tuple[int, int]:
    attempts = max(int(os.environ.get("LOGIN_MAX_ATTEMPTS", "5")), 1)
    window = max(int(os.environ.get("LOGIN_WINDOW_SECONDS", "900")), 1)
    return attempts, window


def login_allowed(key: str) -> bool:
    attempts, window = _login_limits()
    cutoff = time.monotonic() - window
    with _login_lock:
        _login_failures[key] = [stamp for stamp in _login_failures.get(key, []) if stamp >= cutoff]
        return len(_login_failures[key]) < attempts


def record_login_failure(key: str) -> None:
    with _login_lock:
        _login_failures[key].append(time.monotonic())


def clear_login_failures(key: str) -> None:
    with _login_lock:
        _login_failures.pop(key, None)


def reset_login_throttle() -> None:
    with _login_lock:
        _login_failures.clear()
