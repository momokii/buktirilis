"""Session and CSRF dependencies shared by mutating routers."""

from __future__ import annotations

from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.deps import Principal, get_principal
from app.models import AuditEvent, Project, ProjectMember, TargetConfig
from app.security import require_csrf as validate_csrf


def csrf_protected(
    request: Request,
    x_csrf_token: str | None = Header(default=None),
    principal: Principal = Depends(get_principal),
) -> Principal:
    validate_csrf(principal.session, x_csrf_token)
    return principal


def record_denial(
    db: Session,
    *,
    principal: Principal,
    project_id=None,
    action: str,
    detail: str,
) -> None:
    db.add(
        AuditEvent(
            actor_id=principal.user.id,
            actor_label=principal.label,
            project_id=project_id,
            action="security.access_denied",
            target_type="route",
            target_id=action[:100],
            metadata_json={"detail": detail[:300]},
            ip_hash=principal.ip_hash,
        )
    )
    db.commit()


def current_target_config(db: Session, project: Project) -> TargetConfig | None:
    return db.execute(
        select(TargetConfig)
        .where(TargetConfig.project_id == project.id)
        .order_by(TargetConfig.revision.desc())
        .limit(1)
    ).scalar_one_or_none()


def membership(db: Session, user_id, project_id):
    return db.execute(
        select(ProjectMember).where(
            ProjectMember.project_id == project_id, ProjectMember.user_id == user_id
        )
    ).scalar_one_or_none()


def forbidden(detail: str = "You do not have permission for this action") -> HTTPException:
    return HTTPException(status_code=403, detail=detail)
