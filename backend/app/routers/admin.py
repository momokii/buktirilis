"""Installation administration: user accounts and scoped project membership."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import Principal, require_admin
from app.domain import AuditAction, Role
from app.models import AuditEvent, Project, ProjectMember, User
from app.routers.auth import normalise_email
from app.security import hash_password
from app.serializers import iso, user_row

ROUTER = APIRouter(prefix="/admin", tags=["admin"])


class MembershipInput(BaseModel):
    project_id: uuid.UUID
    role: Role


class UserCreate(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    display_name: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=12, max_length=512)
    is_admin: bool = False
    memberships: list[MembershipInput] = []


class UserUpdate(BaseModel):
    display_name: str | None = Field(default=None, max_length=120)
    password: str | None = Field(default=None, min_length=12, max_length=512)
    is_admin: bool | None = None
    is_active: bool | None = None


@ROUTER.get("/users")
def list_users(
    db: Session = Depends(get_db), principal: Principal = Depends(require_admin)
) -> dict:
    users = list(db.execute(select(User).order_by(User.created_at)).scalars())
    memberships: dict[str, list[dict]] = {}
    for member in db.execute(select(ProjectMember)).scalars():
        project = db.get(Project, member.project_id)
        memberships.setdefault(str(member.user_id), []).append(
            {
                "project_id": str(member.project_id),
                "project_name": project.name if project else "",
                "role": member.role,
            }
        )
    return {
        "items": [
            {**user_row(user), "memberships": memberships.get(str(user.id), [])} for user in users
        ]
    }


@ROUTER.post("/users", status_code=201)
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_admin),
) -> dict:
    email = normalise_email(payload.email)
    if db.execute(select(User).where(User.email == email)).scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail="An account with this email already exists")
    user = User(
        email=email,
        display_name=payload.display_name.strip(),
        password_hash=hash_password(payload.password),
        is_admin=payload.is_admin,
        is_active=True,
    )
    db.add(user)
    db.flush()
    for membership in payload.memberships:
        project = db.get(Project, membership.project_id)
        if project is None:
            raise HTTPException(status_code=422, detail="Project not found for a membership")
        db.add(
            ProjectMember(
                project_id=project.id,
                user_id=user.id,
                role=membership.role.value,
                added_by=principal.user.id,
            )
        )
    db.add(
        AuditEvent(
            actor_id=principal.user.id,
            actor_label=principal.label,
            action=AuditAction.USER_CREATED.value,
            target_type="user",
            target_id=str(user.id),
            metadata_json={
                "is_admin": payload.is_admin,
                "memberships": [
                    {"project_id": str(m.project_id), "role": m.role.value}
                    for m in payload.memberships
                ],
            },
        )
    )
    db.commit()
    return user_row(user)


@ROUTER.patch("/users/{user_id}")
def update_user(
    user_id: uuid.UUID,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_admin),
) -> dict:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    if user.id == principal.user.id and payload.is_admin is False:
        raise HTTPException(status_code=409, detail="You cannot remove your own administrator role")
    if user.id == principal.user.id and payload.is_active is False:
        raise HTTPException(status_code=409, detail="You cannot deactivate your own account")
    if payload.display_name is not None:
        user.display_name = payload.display_name.strip()
    if payload.password is not None:
        user.password_hash = hash_password(payload.password)
    if payload.is_admin is not None:
        user.is_admin = payload.is_admin
    if payload.is_active is not None:
        user.is_active = payload.is_active
    db.add(
        AuditEvent(
            actor_id=principal.user.id,
            actor_label=principal.label,
            action=AuditAction.USER_UPDATED.value,
            target_type="user",
            target_id=str(user.id),
            metadata_json={
                "fields": [
                    key
                    for key, value in payload.model_dump(exclude_none=True).items()
                    if key != "password"
                ],
                "password_rotated": payload.password is not None,
            },
        )
    )
    db.commit()
    return {**user_row(user), "updated_at": iso(user.created_at)}


@ROUTER.get("/audit")
def audit_tail(
    limit: int = 50,
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_admin),
) -> dict:
    rows = list(
        db.execute(
            select(AuditEvent).order_by(AuditEvent.at.desc()).limit(min(max(limit, 1), 200))
        ).scalars()
    )
    return {
        "items": [
            {
                "id": str(row.id),
                "at": iso(row.at),
                "actor": row.actor_label,
                "action": row.action,
                "target_type": row.target_type,
                "target_id": row.target_id,
                "project_id": str(row.project_id) if row.project_id else None,
                "metadata": row.metadata_json,
            }
            for row in rows
        ]
    }
