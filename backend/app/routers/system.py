"""Health, installation metadata, and worker status."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.deps import Principal, get_principal
from app.models import Job, Run
from app.services.profiles import list_profiles, profile_as_json
from app.services.queue import queued_counts

ROUTER = APIRouter(tags=["system"])


@ROUTER.get("/health")
def health(db: Session = Depends(get_db)) -> dict:
    db.execute(select(func.now()))
    return {"status": "ok", "service": "buktirilis-api"}


@ROUTER.get("/system/meta")
def meta(principal: Principal = Depends(get_principal)) -> dict:
    settings = get_settings()
    return {
        "product": "BuktiRilis",
        "app_env": settings.app_env,
        "demo_enabled": settings.demo_enabled,
        "live_enabled": settings.live_enabled,
        "live_requires": [
            "LIVE_EXECUTION_ENABLED=true",
            "STRIX_MODEL set on the worker",
            "Pinned Strix CLI and container runtime on the worker host",
        ],
        "strix_version": settings.strix_version,
        "profiles": [profile_as_json(profile) for profile in list_profiles()],
        "depths": ["quick", "standard"],
        "export_formats": ["pdf", "csv", "json"],
        "evidence_retention_days": settings.evidence_retention_days,
        "notice": "This installation is not a compliance certification product.",
    }


@ROUTER.get("/system/worker")
def worker_status(
    principal: Principal = Depends(get_principal), db: Session = Depends(get_db)
) -> dict:
    counts = queued_counts(db)
    recent_jobs = list(db.execute(select(Job).order_by(Job.created_at.desc()).limit(5)).scalars())
    active_runs = list(
        db.execute(
            select(Run).where(Run.status.in_(["queued", "running", "cancel_requested"]))
        ).scalars()
    )
    return {
        **counts,
        "active_runs": len(active_runs),
        "jobs": [
            {
                "id": str(job.id),
                "kind": job.kind,
                "state": job.state,
                "attempts": job.attempts,
                "error_code": job.error_code,
                "claimed_by": job.claimed_by,
            }
            for job in recent_jobs
        ],
    }
