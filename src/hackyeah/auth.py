"""SQLite-backed authentication and sessions."""

import os
from collections import deque
from datetime import UTC, datetime, timedelta
from hashlib import pbkdf2_hmac
from secrets import compare_digest, token_bytes, token_urlsafe
from time import monotonic
from uuid import uuid4

from fastapi import HTTPException, Request, Response

from hackyeah import models as m
from hackyeah.database import Store, atomic

COOKIE_NAME = "hackyeah_session"
SESSION_SECONDS = 86400
COOKIE_SECURE = os.environ.get("SESSION_COOKIE_SECURE", "true").lower() != "false"
users = Store[str, tuple[m.User, bytes, bytes]]("auth.users")
sessions = Store[str, tuple[m.Session, datetime]]("auth.sessions")
_attempts: dict[tuple[str, str], deque[float]] = {}
_lock = atomic


def check_origin(request: Request) -> None:
    origin = request.headers.get("origin")
    if origin is not None and origin != str(request.base_url).rstrip("/"):
        raise HTTPException(403, detail="FORBIDDEN")


def _rate_limit(request: Request, operation: str) -> None:
    key = (request.client.host if request.client else "unknown", operation)
    now = monotonic()
    with _lock:
        # ponytail: process-local limits; use a shared limiter with multiple workers.
        for stale in list(_attempts):
            if not _attempts[stale] or _attempts[stale][-1] <= now - 60:
                del _attempts[stale]
        attempts = _attempts.setdefault(key, deque())
        while attempts and attempts[0] <= now - 60:
            attempts.popleft()
        if len(attempts) >= 10:
            raise HTTPException(
                429, detail="RATE_LIMITED", headers={"Retry-After": "60"}
            )
        attempts.append(now)


def _hash(password: str, salt: bytes) -> bytes:
    return pbkdf2_hmac("sha256", password.encode(), salt, 600_000)


def register(body: m.RegisterRequest, request: Request, response: Response) -> m.User:
    check_origin(request)
    _rate_limit(request, "register")
    email = str(body.email).casefold()
    salt = token_bytes(16)
    password_hash = _hash(body.password.get_secret_value(), salt)
    with _lock:
        if email in users:
            raise HTTPException(409, detail="CONFLICT")
        user = m.User(id=uuid4().hex, display_name=body.display_name, roles=["user"])
        users[email] = (user, salt, password_hash)
    response.headers["Cache-Control"] = "no-store"
    return user.model_copy(deep=True)


def login(body: m.LoginRequest, request: Request, response: Response) -> m.Session:
    check_origin(request)
    _rate_limit(request, "login")
    with _lock:
        account = users.get(str(body.email).casefold())
    salt, expected = (account[1], account[2]) if account else (bytes(16), bytes(32))
    supplied = _hash(body.password.get_secret_value(), salt)
    if not compare_digest(supplied, expected) or account is None:
        raise HTTPException(401, detail="INVALID_CREDENTIALS")
    session = m.Session(
        user=account[0].model_copy(deep=True), csrf_token=token_urlsafe(32)
    )
    token = token_urlsafe(32)
    with _lock:
        now = datetime.now(UTC)
        for expired in list(sessions):
            if sessions[expired][1] <= now:
                del sessions[expired]
        sessions.pop(request.cookies.get(COOKIE_NAME, ""), None)
        sessions[token] = (session, now + timedelta(seconds=SESSION_SECONDS))
    response.set_cookie(
        COOKIE_NAME,
        token,
        max_age=SESSION_SECONDS,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="lax",
        path="/",
    )
    response.headers["Cache-Control"] = "no-store"
    return session.model_copy(deep=True)


def get_session(request: Request) -> m.Session:
    token = request.cookies.get(COOKIE_NAME, "")
    with _lock:
        stored = sessions.get(token)
        if stored is None or stored[1] <= datetime.now(UTC):
            sessions.pop(token, None)
            raise HTTPException(401, detail="UNAUTHORIZED")
        return stored[0].model_copy(deep=True)


def require_session(request: Request) -> m.User:
    return get_session(request).user


def require_csrf(request: Request) -> m.User:
    check_origin(request)
    session = get_session(request)
    if not compare_digest(
        request.headers.get("X-CSRF-Token", "").encode(), session.csrf_token.encode()
    ):
        raise HTTPException(403, detail="FORBIDDEN")
    return session.user


def logout(request: Request, response: Response) -> None:
    require_csrf(request)
    with _lock:
        sessions.pop(request.cookies.get(COOKIE_NAME, ""), None)
    response.delete_cookie(
        COOKIE_NAME, path="/", secure=COOKIE_SECURE, httponly=True, samesite="lax"
    )
    response.headers["Cache-Control"] = "no-store"
