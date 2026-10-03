from __future__ import annotations

import os
import secrets
from datetime import UTC, datetime, timedelta

import jwt
from fastapi import Cookie, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from .auth_context import AuthContext, resolve_employee_context
from .database import SessionLocal
from .security import JWT_ALGORITHM, jwt_secret

COMPANY_CHALLENGE_COOKIE = "pom_company_challenge"
EMPLOYEE_SESSION_COOKIE = "pom_session"
COMPANY_CHALLENGE_MINUTES = 10
EMPLOYEE_SESSION_HOURS = 12


def cookie_secure() -> bool:
    return os.environ.get("WEB_COOKIE_SECURE", "true").strip().lower() not in {"0", "false", "no"}


def _encode(claims: dict, lifetime: timedelta) -> str:
    now = datetime.now(UTC)
    return jwt.encode({**claims, "iat": now, "exp": now + lifetime}, jwt_secret(), algorithm=JWT_ALGORITHM)


def create_company_challenge(company_id: str) -> str:
    return _encode(
        {"type": "web_company_challenge", "company_id": company_id},
        timedelta(minutes=COMPANY_CHALLENGE_MINUTES),
    )


def create_employee_session(auth: AuthContext) -> tuple[str, str]:
    csrf = secrets.token_urlsafe(32)
    token = _encode(
        {
            "type": "web_employee_session",
            "company_id": auth.company_id,
            "employee_id": auth.employee_id,
            "role": auth.role,
            "location_id": auth.location_id,
            "auth_version": auth.auth_version,
            "csrf": csrf,
        },
        timedelta(hours=EMPLOYEE_SESSION_HOURS),
    )
    return token, csrf


def decode_web_token(token: str, expected_type: str) -> dict:
    try:
        claims = jwt.decode(token, jwt_secret(), algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(401, "Browser sign-in expired") from exc
    except jwt.InvalidTokenError as exc:
        raise HTTPException(401, "Invalid browser sign-in") from exc
    if claims.get("type") != expected_type:
        raise HTTPException(401, "Invalid browser sign-in")
    return claims


def resolve_web_session(db: Session, token: str) -> tuple[AuthContext, dict]:
    claims = decode_web_token(token, "web_employee_session")
    employee_claims = dict(claims)
    employee_claims["type"] = "employee"
    return resolve_employee_context(db, employee_claims), claims


def require_csrf(claims: dict, csrf_header: str) -> None:
    expected = claims.get("csrf", "")
    if not expected or not csrf_header or not secrets.compare_digest(expected, csrf_header):
        raise HTTPException(403, "CSRF validation failed")


def get_web_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def web_auth_context(
    session_token: str = Cookie(default="", alias=EMPLOYEE_SESSION_COOKIE),
    db: Session = Depends(get_web_db),
) -> AuthContext:
    auth, _claims = resolve_web_session(db, session_token)
    return auth


def web_mutation_context(
    session_token: str = Cookie(default="", alias=EMPLOYEE_SESSION_COOKIE),
    csrf_token: str = Header(default="", alias="X-CSRF-Token"),
    db: Session = Depends(get_web_db),
) -> AuthContext:
    auth, claims = resolve_web_session(db, session_token)
    require_csrf(claims, csrf_token)
    return auth
