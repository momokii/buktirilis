"""Authentication, session, CSRF, credential-encryption, and rate-limit helpers."""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from cryptography.fernet import Fernet, InvalidToken
from fastapi import HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import LoginAttempt, User, UserSession

_hasher = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=4)


def hash_password(password: str) -> str:
    if len(password) < 12:
        raise ValueError("password must be at least 12 characters")
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def needs_rehash(password_hash: str) -> bool:
    try:
        return _hasher.check_needs_rehash(password_hash)
    except InvalidHashError:
        return True


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def hash_ip(address: str) -> str:
    """Pseudonymous client identifier for rate limits and audit events."""
    secret = get_settings().secret_key.encode("utf-8")
    return hmac.new(secret, address.encode("utf-8"), hashlib.sha256).hexdigest()


def _fernet() -> Fernet:
    key = hashlib.sha256(get_settings().secret_key.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(key))


def encrypt_secret(value: str) -> str:
    return _fernet().encrypt(value.encode("utf-8")).decode("ascii")


def decrypt_secret(ciphertext: str) -> str:
    try:
        return _fernet().decrypt(ciphertext.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError) as exc:  # pragma: no cover - defensive
        raise RuntimeError(
            "stored credential cannot be decrypted with this deployment key"
        ) from exc


def create_session(
    db: Session,
    user: User,
    *,
    user_agent: str | None = None,
    ip: str | None = None,
) -> tuple[str, UserSession]:
    settings = get_settings()
    raw_token = secrets.token_urlsafe(48)
    csrf = secrets.token_urlsafe(32)
    now = datetime.now(UTC)
    session = UserSession(
        user_id=user.id,
        token_hash=hash_token(raw_token),
        csrf_token=csrf,
        created_at=now,
        last_seen_at=now,
        expires_at=now + timedelta(hours=settings.session_ttl_hours),
        user_agent_hash=hashlib.sha256((user_agent or "").encode()).hexdigest()
        if user_agent
        else None,
    )
    db.add(session)
    db.flush()
    return raw_token, session


def revoke_session(db: Session, session: UserSession) -> None:
    session.revoked_at = datetime.now(UTC)
    db.add(session)
    db.flush()


def resolve_session(db: Session, raw_token: str | None) -> tuple[UserSession, User] | None:
    if not raw_token:
        return None
    token_hash = hash_token(raw_token)
    row = db.execute(
        select(UserSession, User)
        .join(User, User.id == UserSession.user_id)
        .where(UserSession.token_hash == token_hash)
    ).first()
    if row is None:
        return None
    session, user = row
    now = datetime.now(UTC)
    if session.revoked_at is not None or session.expires_at <= now or not user.is_active:
        return None
    if now - session.last_seen_at > timedelta(minutes=5):
        session.last_seen_at = now
        db.add(session)
    return session, user


def require_csrf(session: UserSession, provided: str | None) -> None:
    if not provided or not secrets.compare_digest(session.csrf_token, provided):
        raise HTTPException(status_code=403, detail="Missing or invalid CSRF token")


def check_login_rate_limit(db: Session, email: str, ip_hash_value: str) -> None:
    settings = get_settings()
    window_start = datetime.now(UTC) - timedelta(seconds=settings.login_rate_limit_window_seconds)
    failures = db.execute(
        select(func.count())
        .select_from(LoginAttempt)
        .where(
            LoginAttempt.at >= window_start,
            LoginAttempt.succeeded.is_(False),
            or_(LoginAttempt.email == email, LoginAttempt.ip_hash == ip_hash_value),
        )
    ).scalar_one()
    if failures >= settings.login_rate_limit_max_failures:
        raise HTTPException(
            status_code=429,
            detail="Too many failed sign-in attempts. Try again later or contact an administrator.",
            headers={"Retry-After": str(settings.login_rate_limit_window_seconds)},
        )


def record_login_attempt(db: Session, email: str, ip_hash_value: str, *, succeeded: bool) -> None:
    db.add(
        LoginAttempt(
            email=email,
            ip_hash=ip_hash_value,
            succeeded=succeeded,
            at=datetime.now(UTC),
        )
    )
    db.flush()
