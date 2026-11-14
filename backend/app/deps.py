"""Server-side authorization boundaries.

Role ranking is deliberately monotonic for read-style capabilities; a mutation that
needs a narrower capability declares it explicitly.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.domain import Role
from app.models import Project, ProjectMember, User, UserSession
from app.security import hash_ip, resolve_session

ROLE_RANK = {Role.VIEWER: 1, Role.DEVELOPER: 2, Role.OPERATOR: 3}


@dataclass(frozen=True)
class Principal:
    user: User
    session: UserSession
    ip_hash: str

    @property
    def label(self) -> str:
        return self.user.display_name or self.user.email


def _read_cookie(request: Request) -> str | None:
    from app.config import get_settings

    return request.cookies.get(get_settings().cookie_name)


def get_principal(
    request: Request,
    db: Session = Depends(get_db),
) -> Principal:
    resolved = resolve_session(db, _read_cookie(request))
    if resolved is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    session, user = resolved
    db.commit()
    client = request.client.host if request.client else "unknown"
    return Principal(user=user, session=session, ip_hash=hash_ip(client))


def require_admin(principal: Principal = Depends(get_principal)) -> Principal:
    if not principal.user.is_admin:
        raise HTTPException(status_code=403, detail="Administrator access required")
    return principal


@dataclass(frozen=True)
class ProjectAccess:
    project: Project
    role: Role
    principal: Principal

    @property
    def is_admin(self) -> bool:
        return self.principal.user.is_admin

    def can(self, minimum: Role) -> bool:
        return self.principal.user.is_admin or ROLE_RANK[self.role] >= ROLE_RANK[minimum]


def project_role(db: Session, user: User, project_id: uuid.UUID) -> Role | None:
    row = db.execute(
        select(ProjectMember.role).where(
            ProjectMember.project_id == project_id, ProjectMember.user_id == user.id
        )
    ).scalar_one_or_none()
    if row is None:
        return None
    try:
        return Role(row)
    except ValueError:
        return None


def load_project_access(db: Session, principal: Principal, project_id: uuid.UUID) -> ProjectAccess:
    project = db.get(Project, project_id)
    if project is None:
        # Same response for absent and unauthorized projects.
        raise HTTPException(status_code=404, detail="Project not found")
    if principal.user.is_admin:
        return ProjectAccess(project=project, role=Role.OPERATOR, principal=principal)
    role = project_role(db, principal.user, project_id)
    if role is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return ProjectAccess(project=project, role=role, principal=principal)


def require_project(minimum: Role):
    def dependency(
        project_id: uuid.UUID,
        principal: Principal = Depends(get_principal),
        db: Session = Depends(get_db),
    ) -> ProjectAccess:
        access = load_project_access(db, principal, project_id)
        if not access.can(minimum):
            raise HTTPException(
                status_code=403,
                detail=f"Requires the {minimum.value} role on this project",
            )
        return access

    return dependency


def require_any_project_role(principal: Principal, db: Session) -> list[Project]:
    if principal.user.is_admin:
        return list(db.execute(select(Project).order_by(Project.name)).scalars())
    return list(
        db.execute(
            select(Project)
            .join(ProjectMember, ProjectMember.project_id == Project.id)
            .where(ProjectMember.user_id == principal.user.id)
            .order_by(Project.name)
        ).scalars()
    )
