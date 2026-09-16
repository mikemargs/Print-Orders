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
) -> str:
    now = datetime.now(UTC)
    lifetime = lifetime or (timedelta(days=365) if token_type == "company" else timedelta(hours=16))
    return jwt.encode(
        {
            "company_id": company_id,
            "type": token_type,
            "employee_id": employee_id,
            "role": role,
            "iat": now,
            "exp": now + lifetime,
        },
        jwt_secret(),
        algorithm=JWT_ALGORITHM,
    )


def decode_token(token: str) -> dict:
    return jwt.decode(token, jwt_secret(), algorithms=[JWT_ALGORITHM])
