from __future__ import annotations

import jwt
from fastapi import Cookie, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from .auth_context import AuthContext, resolve_employee_context
from .security import decode_token
from .web_sessions import EMPLOYEE_SESSION_COOKIE, get_web_db, require_csrf, resolve_web_session


def _bearer_claims(authorization: str) -> dict:
    if not authorization.startswith("Bearer "):
        return {}
    try:
        return decode_token(authorization[7:])
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(401, "Sign-in expired") from exc
    except (jwt.InvalidTokenError, RuntimeError) as exc:
        raise HTTPException(401, "Invalid sign-in") from exc


def hybrid_context(
    authorization: str = Header(default=""),
    session_token: str = Cookie(default="", alias=EMPLOYEE_SESSION_COOKIE),
    db: Session = Depends(get_web_db),
) -> AuthContext:
    claims = _bearer_claims(authorization)
    if claims:
        return resolve_employee_context(db, claims)
    if session_token:
        auth, _claims = resolve_web_session(db, session_token)
        return auth
    raise HTTPException(401, "Sign-in required")


def hybrid_mutation_context(
    authorization: str = Header(default=""),
    session_token: str = Cookie(default="", alias=EMPLOYEE_SESSION_COOKIE),
    csrf_token: str = Header(default="", alias="X-CSRF-Token"),
    db: Session = Depends(get_web_db),
) -> AuthContext:
    claims = _bearer_claims(authorization)
    if claims:
        return resolve_employee_context(db, claims)
    if session_token:
        auth, web_claims = resolve_web_session(db, session_token)
        require_csrf(web_claims, csrf_token)
        return auth
    raise HTTPException(401, "Sign-in required")


def hybrid_admin(auth: AuthContext = Depends(hybrid_context)) -> AuthContext:
    if auth.role != "admin":
        raise HTTPException(403, "Administrator permission required")
    return auth


def hybrid_admin_mutation(auth: AuthContext = Depends(hybrid_mutation_context)) -> AuthContext:
    if auth.role != "admin":
        raise HTTPException(403, "Administrator permission required")
    return auth


def hybrid_supervisor(auth: AuthContext = Depends(hybrid_context)) -> AuthContext:
    if auth.role not in {"supervisor", "admin"}:
        raise HTTPException(403, "Supervisor permission required")
    return auth
