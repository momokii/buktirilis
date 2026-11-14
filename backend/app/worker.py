"""Worker entrypoint: claim jobs, execute runs and retests, reconcile lost leases."""

from __future__ import annotations

import logging
import signal
import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager

from app.config import get_settings
from app.db import session_scope
from app.services.pipeline import run_job
from app.services.queue import claim_next, heartbeat, reconcile

logger = logging.getLogger("buktirilis.worker")
_shutdown = {"requested": False}


def _handle_signal(signum, frame) -> None:
    _shutdown["requested"] = True
    logger.info("worker shutdown requested (signal %s)", signum)


@contextmanager
def _lease_heartbeat(job_id) -> Iterator[None]:
    """Keep the claim lease alive for the whole job rather than per stage."""
    import threading

    stop = threading.Event()
    settings = get_settings()

    def beat() -> None:
        while not stop.wait(15):
            try:
                with session_scope() as db:
                    from app.models import Job

                    job = db.get(Job, job_id)
                    if job is not None and job.state == "running":
                        heartbeat(db, job=job, settings=settings)
            except Exception:
                logger.warning("heartbeat failed for job %s", job_id)

    thread = threading.Thread(target=beat, name="lease-heartbeat", daemon=True)
    thread.start()
    try:
        yield
    finally:
        stop.set()


def process_once(*, worker_id: str) -> bool:
    settings = get_settings()
    with session_scope() as db:
        job = claim_next(db, worker_id=worker_id, settings=settings)
        job_id = job.id if job is not None else None
    if job_id is None:
        return False
    try:
        with _lease_heartbeat(job_id), session_scope() as db:
            from app.models import Job

            job = db.get(Job, job_id)
            if job is None:
                return True
            logger.info("claimed job %s (%s)", job.id, job.kind)
            run_job(db, job=job, settings=settings)
        return True
    except Exception:
        logger.exception("job %s failed unexpectedly", job_id)
        with session_scope() as db:
            from app.models import Job, Run

            job = db.get(Job, job_id)
            if job is not None and job.state not in {
                "succeeded",
                "failed",
                "canceled",
                "interrupted",
            }:
                job.state = "failed"
                job.error_code = "worker_exception"
                job.error_detail = "The worker raised an unexpected error; inspect server logs."
                job.finished_at = job.finished_at or __import__("app.models").models.utcnow()
                if job.run_id is not None:
                    run = db.get(Run, job.run_id)
                    if run is not None and run.status in {"queued", "running", "cancel_requested"}:
                        run.status = "failed"
                        run.failure_reason = "The worker raised an unexpected error. Partial results remain viewable."
                        run.completed_at = (
                            run.completed_at or __import__("app.models").models.utcnow()
                        )
        return True


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    settings = get_settings()
    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)
    logger.info(
        "worker %s starting (mode=%s, demo=%s, live=%s)",
        settings.worker_id,
        settings.app_env,
        settings.demo_enabled,
        settings.live_enabled,
    )
    with session_scope() as db:
        reconciled = reconcile(db, worker_id=settings.worker_id)
        if reconciled:
            logger.warning("reconciled %d stale job lease(s): %s", len(reconciled), reconciled)
    idle_since = time.monotonic()
    while not _shutdown["requested"]:
        worked = process_once(worker_id=settings.worker_id)
        if not worked:
            time.sleep(settings.worker_poll_seconds)
            if time.monotonic() - idle_since > 60:
                with session_scope() as db:
                    reconcile(db, worker_id=settings.worker_id)
                idle_since = time.monotonic()
        else:
            idle_since = time.monotonic()
    logger.info("worker %s stopped", settings.worker_id)
    return 0


if __name__ == "__main__":
    sys.exit(main())
