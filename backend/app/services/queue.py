"""Database-backed job queue with a claim lease and interrupted-execution reconciliation."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.domain import RunStatus
from app.models import Activity, AuditEvent, Job, Run


def utcnow() -> datetime:
    return datetime.now(UTC)


def claim_next(db: Session, *, worker_id: str, settings: Settings) -> Job | None:
    now = utcnow()
    job = db.execute(
        select(Job)
        .where(Job.state == "queued", Job.available_at <= now)
        .order_by(Job.available_at, Job.created_at)
        .limit(1)
        .with_for_update(skip_locked=True)
    ).scalar_one_or_none()
    if job is None:
        return None
    job.state = "running"
    job.claimed_by = worker_id
    job.attempts = int(job.attempts or 0) + 1
    job.started_at = job.started_at or now
    job.heartbeat_at = now
    job.lease_expires_at = now + timedelta(seconds=settings.worker_lease_seconds)
    db.flush()
    return job


def heartbeat(db: Session, *, job: Job, settings: Settings) -> None:
    job.heartbeat_at = utcnow()
    job.lease_expires_at = utcnow() + timedelta(seconds=settings.worker_lease_seconds)
    db.flush()


def is_cancel_requested(db: Session, job_id: uuid.UUID) -> bool:
    state = db.execute(select(Job.state).where(Job.id == job_id)).scalar_one_or_none()
    if state == "cancel_requested":
        return True
    run_id = db.execute(select(Job.run_id).where(Job.id == job_id)).scalar_one_or_none()
    if run_id is not None:
        run_status = db.execute(select(Run.status).where(Run.id == run_id)).scalar_one_or_none()
        return run_status == RunStatus.CANCEL_REQUESTED.value
    return False


def finish_job(
    db: Session,
    *,
    job: Job,
    state: str,
    error_code: str | None = None,
    error_detail: str | None = None,
) -> None:
    job.state = state
    job.error_code = error_code
    job.error_detail = (error_detail or "")[:1000] or None
    job.finished_at = utcnow()
    job.lease_expires_at = None
    db.flush()


def requeue_job(db: Session, *, job: Job, settings: Settings, delay_seconds: int = 5) -> None:
    job.state = "queued"
    job.claimed_by = None
    job.lease_expires_at = None
    job.available_at = utcnow() + timedelta(seconds=delay_seconds)
    db.flush()


def reconcile(db: Session, *, worker_id: str) -> list[str]:
    """Mark expired leases as interrupted; never silently re-run uncertain work."""
    now = utcnow()
    # Safety net for cancel requests that were queued but never claimed.
    for job in db.execute(
        select(Job).where(Job.state == "cancel_requested", Job.lease_expires_at.is_(None))
    ).scalars():
        finish_job(db, job=job, state="canceled", error_code="canceled")
        _terminal_run(
            db,
            job,
            status=RunStatus.CANCELED,
            detail="Cancellation was requested before a worker claimed the job.",
        )
    expired = list(
        db.execute(
            select(Job).where(
                Job.state.in_(["running", "cancel_requested"]),
                Job.lease_expires_at.is_not(None),
                Job.lease_expires_at < now,
            )
        ).scalars()
    )
    reconciled: list[str] = []
    for job in expired:
        if job.state == "cancel_requested":
            finish_job(db, job=job, state="canceled", error_code="canceled")
            _terminal_run(
                db,
                job,
                status=RunStatus.CANCELED,
                detail="Cancellation completed after the worker lease expired.",
            )
            reconciled.append(f"canceled:{job.id}")
            continue
        if job.claimed_by == worker_id:
            # Our own lease cannot expire while this process holds the job, but a
            # clock jump should still fail closed.
            continue
        finish_job(
            db,
            job=job,
            state="interrupted",
            error_code="worker_lease_expired",
            error_detail=(
                "The worker stopped heartbeating. Execution is marked interrupted and will not "
                "be redispatched automatically."
            ),
        )
        _terminal_run(
            db,
            job,
            status=RunStatus.INTERRUPTED,
            detail=(
                "Worker lease expired. Partial artifacts, if any, remain viewable with an "
                "incomplete label. Retry only after confirming the earlier execution stopped."
            ),
        )
        reconciled.append(f"interrupted:{job.id}")
    return reconciled


def _terminal_run(db: Session, job: Job, *, status: RunStatus, detail: str) -> None:
    if job.run_id is None:
        return
    run = db.get(Run, job.run_id)
    if run is None:
        return
    if run.status in {
        RunStatus.COMPLETED.value,
        RunStatus.FAILED.value,
        RunStatus.CANCELED.value,
        RunStatus.INTERRUPTED.value,
    }:
        return
    run.status = status.value
    run.completed_at = run.completed_at or utcnow()
    run.snapshot_at = run.snapshot_at or run.completed_at
    run.failure_reason = detail
    db.add(
        Activity(
            run_id=run.id,
            level="error",
            code=f"run.{status.value}",
            message=detail[:900],
        )
    )
    db.add(
        AuditEvent(
            project_id=run.project_id,
            action=f"run.{status.value}",
            target_type="run",
            target_id=str(run.id),
            metadata_json={"reason": "worker_lease_expired"},
        )
    )
    db.flush()


def queued_counts(db: Session) -> dict[str, Any]:
    jobs = db.execute(select(Job).where(Job.state.in_(["queued", "running"]))).scalars().all()
    return {
        "queued": sum(1 for job in jobs if job.state == "queued"),
        "running": sum(1 for job in jobs if job.state == "running"),
    }
