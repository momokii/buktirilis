"""Authentication: bootstrap, login, logout, and session discovery."""

from __future__ import annotations

import re
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.deps import Principal, get_principal
from app.models import AuditEvent, Project, ProjectMember, User, UserSession
from app.routers.deps import csrf_protected
from app.security import (
    check_login_rate_limit,
    create_session,
    hash_ip,
    hash_password,
    needs_rehash,
    record_login_attempt,
    revoke_session,
    verify_password,
)

ROUTER = APIRouter(tags=["auth"])
EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=512)


class BootstrapRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    display_name: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=12, max_length=512)


def normalise_email(value: str) -> str:
    email = value.strip().lower()
    if not EMAIL_RE.fullmatch(email):
        raise HTTPException(status_code=422, detail="Enter a valid email address")
    return email


def set_session_cookie(response: Response, token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        key=settings.cookie_name,
        value=token,
        httponly=True,
        secure=bool(settings.cookie_secure),
        samesite=settings.cookie_samesite,
        max_age=settings.session_ttl_hours * 3600,
        path="/",
    )


def session_payload(db: Session, principal: Principal) -> dict:
    projects = (
        list(db.execute(select(Project).order_by(Project.name)).scalars())
        if principal.user.is_admin
        else list(
            db.execute(
                select(Project)
                .join(ProjectMember, ProjectMember.project_id == Project.id)
                .where(ProjectMember.user_id == principal.user.id)
                .order_by(Project.name)
            ).scalars()
        )
    )
    memberships = {
        str(project_id): role
        for project_id, role in db.execute(
            select(ProjectMember.project_id, ProjectMember.role).where(
                ProjectMember.user_id == principal.user.id
            )
        ).all()
    }
    return {
        "user": {
            "id": str(principal.user.id),
            "email": principal.user.email,
            "display_name": principal.user.display_name,
            "is_admin": principal.user.is_admin,
        },
        "csrf_token": principal.session.csrf_token,
        "projects": [
            {
                "id": str(project.id),
                "slug": project.slug,
                "name": project.name,
                "role": "admin" if principal.user.is_admin else memberships.get(str(project.id)),
            }
            for project in projects
        ],
        "environment": {
            "app_env": get_settings().app_env,
            "demo_enabled": get_settings().demo_enabled,
            "live_enabled": get_settings().live_enabled,
        },
    }


def web_bootstrap_allowed(settings) -> bool:
    """Only a local development installation may create the first admin over HTTP."""
    return settings.app_env == "development"


@ROUTER.get("/system/bootstrap")
def bootstrap_status(db: Session = Depends(get_db)) -> dict:
    count = db.execute(select(func.count()).select_from(User)).scalar_one()
    settings = get_settings()
    return {
        "needs_bootstrap": count == 0,
        "web_bootstrap_allowed": web_bootstrap_allowed(settings),
        "demo_enabled": settings.demo_enabled,
    }


@ROUTER.post("/auth/bootstrap", status_code=201)
def bootstrap(
    payload: BootstrapRequest,
    response: Response,
    request: Request,
    db: Session = Depends(get_db),
) -> dict:
    settings = get_settings()
    if not web_bootstrap_allowed(settings):
        raise HTTPException(
            status_code=403,
            detail=(
                "Web bootstrap is disabled in this environment. Run "
                "`python -m app.cli bootstrap-admin --email <email>` on the server instead."
            ),
        )
    count = db.execute(select(func.count()).select_from(User)).scalar_one()
    if count > 0:
        raise HTTPException(status_code=409, detail="An administrator already exists")
    email = normalise_email(payload.email)
    user = User(
        email=email,
        display_name=payload.display_name.strip(),
        password_hash=hash_password(payload.password),
        is_admin=True,
        is_active=True,
    )
    db.add(user)
    db.flush()
    raw_token, _session = create_session(
        db,
        user,
        user_agent=request.headers.get("user-agent"),
        ip=request.client.host if request.client else None,
    )
    db.add(
        AuditEvent(
            actor_id=user.id,
            actor_label=user.display_name,
            action="admin.user_created",
            target_type="user",
            target_id=str(user.id),
            metadata_json={"bootstrap": True},
            ip_hash=hash_ip(request.client.host if request.client else "unknown"),
        )
    )
    db.commit()
    set_session_cookie(response, raw_token)
    principal = Principal(user=user, session=_session, ip_hash="")
    return session_payload(db, principal)


@ROUTER.post("/auth/login")
def login(
    payload: LoginRequest,
    response: Response,
    request: Request,
    db: Session = Depends(get_db),
) -> dict:
    email = payload.email.strip().lower()
    client_ip = request.client.host if request.client else "unknown"
    ip_hash_value = hash_ip(client_ip)
    check_login_rate_limit(db, email, ip_hash_value)
    user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
    valid = (
        user is not None
        and user.is_active
        and verify_password(user.password_hash, payload.password)
    )
    if not valid or user is None:
        record_login_attempt(db, email, ip_hash_value, succeeded=False)
        db.add(
            AuditEvent(
                actor_label=email,
                action="auth.login_failed",
                target_type="user",
                target_id=email,
                metadata_json={},
                ip_hash=ip_hash_value,
            )
        )
        db.commit()
        raise HTTPException(status_code=401, detail="Email or password is incorrect")
    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(payload.password)
    record_login_attempt(db, email, ip_hash_value, succeeded=True)
    raw_token, session = create_session(
        db, user, user_agent=request.headers.get("user-agent"), ip=client_ip
    )
    db.add(
        AuditEvent(
            actor_id=user.id,
            actor_label=user.display_name,
            action="auth.login_succeeded",
            target_type="user",
            target_id=str(user.id),
            metadata_json={},
            ip_hash=ip_hash_value,
        )
    )
    db.commit()
    set_session_cookie(response, raw_token)
    return session_payload(db, Principal(user=user, session=session, ip_hash=ip_hash_value))


@ROUTER.post("/auth/logout")
def logout(
    response: Response,
    db: Session = Depends(get_db),
    principal: Principal = Depends(csrf_protected),
) -> dict:
    revoke_session(db, principal.session)
    db.add(
        AuditEvent(
            actor_id=principal.user.id,
            actor_label=principal.label,
            action="auth.logout",
            target_type="session",
            target_id=str(principal.session.id),
            metadata_json={},
        )
    )
    db.commit()
    response.delete_cookie(get_settings().cookie_name, path="/")
    return {"ok": True}


@ROUTER.get("/auth/session")
def read_session(
    db: Session = Depends(get_db), principal: Principal = Depends(get_principal)
) -> dict:
    db.commit()
    return session_payload(db, principal)


_ = (UserSession, datetime, UTC)
