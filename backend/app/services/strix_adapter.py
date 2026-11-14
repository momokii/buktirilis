"""Narrow adapter around the self-hosted Strix CLI.

The adapter owns argv construction, a dedicated per-run directory, lifecycle and
exit-code normalisation, cancellation, and artifact discovery. It never passes
browser/user input as flags and never logs credentials.

Contract pinned to Strix ``v1.7.1`` (see docs/strix-contract.md). Live execution is
wired but unverified in this environment; the demo path is the verified one.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import signal
import subprocess
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.config import Settings
from app.domain import Depth

logger = logging.getLogger(__name__)

EXIT_NO_FINDINGS = 0
EXIT_FATAL = 1
EXIT_FINDINGS = 2
MAX_LOG_BYTES = 2 * 1024 * 1024


@dataclass
class LivePreflight:
    checks: list[dict[str, Any]] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return all(check["status"] != "fail" for check in self.checks)


@dataclass
class LiveResult:
    exit_code: int | None
    artifacts_dir: str
    timed_out: bool = False
    canceled: bool = False
    launch_error: str = ""
    cleanup_confirmed: bool = True
    raw_status: str = ""
    log_tail: str = ""
    duration_seconds: int = 0

    @property
    def terminal_state(self) -> str:
        if self.canceled:
            return "canceled"
        if self.timed_out:
            return "interrupted"
        if self.launch_error:
            return "failed"
        if self.exit_code in {EXIT_NO_FINDINGS, EXIT_FINDINGS}:
            return "completed"
        return "failed"

    @property
    def had_findings(self) -> bool:
        return self.exit_code == EXIT_FINDINGS


def live_preflight(settings: Settings) -> LivePreflight:
    checks: list[dict[str, Any]] = []
    binary = shutil.which(settings.strix_binary)
    checks.append(
        {
            "code": "strix_binary",
            "label": "Strix CLI available",
            "status": "pass" if binary else "fail",
            "detail": binary or f"{settings.strix_binary} was not found on PATH",
            "recovery": "Install the pinned Strix CLI on the worker host.",
        }
    )
    model_ready = bool(settings.strix_model)
    checks.append(
        {
            "code": "model",
            "label": "Approved model configured",
            "status": "pass" if model_ready else "fail",
            "detail": settings.strix_model or "STRIX_MODEL is not set on the worker",
            "recovery": "Configure the deployment's approved provider and model on the worker.",
        }
    )
    if binary:
        try:
            version = subprocess.run(  # noqa: S603 - fixed argv, no user input
                [binary, "--version"],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            output = (version.stdout or version.stderr).strip()
            checks.append(
                {
                    "code": "strix_version",
                    "label": "Strix version",
                    "status": "pass" if settings.strix_version in output else "warn",
                    "detail": output[:200] or "no version output",
                    "recovery": "Pin the verified release documented in docs/strix-contract.md.",
                }
            )
        except (OSError, subprocess.SubprocessError) as exc:
            checks.append(
                {
                    "code": "strix_version",
                    "label": "Strix version",
                    "status": "fail",
                    "detail": exc.__class__.__name__,
                    "recovery": "Verify the CLI installation on the worker.",
                }
            )
    docker = shutil.which("docker")
    checks.append(
        {
            "code": "container_runtime",
            "label": "Container runtime available to the worker",
            "status": "pass" if docker else "fail",
            "detail": docker or "docker CLI not found on the worker",
            "recovery": "Provision the isolated worker runtime described in docs/deployment.md.",
        }
    )
    return LivePreflight(checks=checks)


def build_argv(
    settings: Settings,
    *,
    target_url: str,
    depth: str,
    budget_usd: float,
    max_turns: int,
    instruction_path: Path,
    spec_path: Path | None = None,
) -> list[str]:
    if depth not in {d.value for d in Depth}:
        raise ValueError("unsupported depth")
    argv = [
        settings.strix_binary,
        "-n",
        "--target",
        target_url,
        "--scan-mode",
        depth,
        "--max-budget",
        f"{budget_usd:.2f}",
        "--max-turns",
        str(int(max_turns)),
        "--instruction-file",
        str(instruction_path),
    ]
    if spec_path is not None:
        argv.extend(["--target", str(spec_path)])
    return argv


def write_instruction(run_dir: Path, *, profile_name: str, approved_origins: list[str]) -> Path:
    """Trusted, worker-authored instruction file. Never includes credentials."""
    path = run_dir / "strix-instruction.md"
    path.write_text(
        "\n".join(
            [
                f"# Focus: {profile_name}",
                "",
                "This is an authorized internal staging assessment. Only the approved",
                "origins below are in scope; do not follow redirects to other hosts:",
                "",
                *[f"- {origin}" for origin in approved_origins],
                "",
                "Focus on cross-account and cross-tenant object access, role-restricted",
                "functions, and authentication prerequisites. Read-only testing only.",
                "Record the surface, actors, approach, and evidence for every check.",
                "Do not write secrets or tokens into findings or artifacts.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def _tail(path: Path, limit: int = 4000) -> str:
    if not path.is_file():
        return ""
    with path.open("rb") as handle:
        handle.seek(0, os.SEEK_END)
        size = handle.tell()
        handle.seek(max(0, size - limit))
        return handle.read().decode("utf-8", errors="replace")


def find_artifacts_dir(run_dir: Path) -> Path | None:
    base = run_dir / "strix_runs"
    if not base.is_dir():
        return None
    candidates = [child for child in base.iterdir() if (child / "run.json").is_file()]
    if not candidates:
        return None
    return max(candidates, key=lambda child: (child / "run.json").stat().st_mtime)


def read_run_record(artifacts_dir: Path) -> dict[str, Any]:
    path = artifacts_dir / "run.json"
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text("utf-8"))
        return payload if isinstance(payload, dict) else {}
    except (ValueError, OSError):
        return {}


def run_live(
    settings: Settings,
    *,
    target_url: str,
    depth: str,
    budget_usd: float,
    max_turns: int,
    approved_origins: list[str],
    profile_name: str,
    run_dir: Path,
    spec_path: Path | None,
    timeout_seconds: int,
    cancel_check: Callable[[], bool],
    heartbeat: Callable[[], None] | None = None,
) -> LiveResult:
    run_dir.mkdir(parents=True, exist_ok=True)
    instruction_path = write_instruction(
        run_dir, profile_name=profile_name, approved_origins=approved_origins
    )
    argv = build_argv(
        settings,
        target_url=target_url,
        depth=depth,
        budget_usd=budget_usd,
        max_turns=max_turns,
        instruction_path=instruction_path,
        spec_path=spec_path,
    )
    stdout_path = run_dir / "engine.stdout.log"
    stderr_path = run_dir / "engine.stderr.log"
    env = {
        "PATH": os.environ.get("PATH", ""),
        "HOME": str(run_dir),
        "LANG": "C.UTF-8",
        "PYTHONUNBUFFERED": "1",
    }
    for passthrough in (
        "STRIX_LLM",
        "LLM_API_KEY",
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "DOCKER_HOST",
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "NO_PROXY",
    ):
        value = os.environ.get(passthrough)
        if value:
            env[passthrough] = value
    started = time.monotonic()
    timed_out = False
    canceled = False
    cleanup_confirmed = True
    with stdout_path.open("wb") as out, stderr_path.open("wb") as err:
        try:
            process = subprocess.Popen(  # noqa: S603 - structured argv, trusted config
                argv,
                cwd=str(run_dir),
                env=env,
                stdout=out,
                stderr=err,
                start_new_session=True,
            )
        except OSError as exc:
            return LiveResult(
                exit_code=None,
                artifacts_dir="",
                launch_error=f"the engine could not be launched ({exc.__class__.__name__})",
            )
        while True:
            if process.poll() is not None:
                break
            if cancel_check():
                canceled = True
                _terminate_group(process)
                break
            if time.monotonic() - started > timeout_seconds:
                timed_out = True
                _terminate_group(process)
                break
            if heartbeat is not None:
                try:
                    heartbeat()
                except Exception:
                    logger.debug("heartbeat callback failed", exc_info=True)
            time.sleep(0.5)
            if stdout_path.stat().st_size > MAX_LOG_BYTES:
                out.flush()
    if cancel_check() and not canceled:
        canceled = True
        _terminate_group(process)
    exit_code = process.returncode
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:  # pragma: no cover - defensive
        cleanup_confirmed = False
    if cleanup_confirmed:
        # Confirm the process group is gone; a sandbox left running is unsafe to redispatch.
        try:
            os.killpg(process.pid, 0)
            cleanup_confirmed = False
        except (ProcessLookupError, PermissionError):
            cleanup_confirmed = True
    artifacts = find_artifacts_dir(run_dir)
    record = read_run_record(artifacts) if artifacts else {}
    return LiveResult(
        exit_code=exit_code,
        artifacts_dir=str(artifacts) if artifacts else "",
        timed_out=timed_out,
        canceled=canceled,
        cleanup_confirmed=cleanup_confirmed,
        raw_status=str(record.get("status") or ""),
        log_tail=_tail(stderr_path) or _tail(stdout_path),
        duration_seconds=int(time.monotonic() - started),
    )


def _terminate_group(process: subprocess.Popen) -> None:
    try:
        os.killpg(os.getpgid(process.pid), signal.SIGTERM)
    except (ProcessLookupError, PermissionError):
        return
    try:
        process.wait(timeout=10)
        return
    except subprocess.TimeoutExpired:
        logger.debug("engine did not exit after SIGTERM; escalating to SIGKILL")
    try:
        os.killpg(os.getpgid(process.pid), signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        return
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:  # pragma: no cover - defensive
        logger.warning("engine process group did not exit after SIGKILL")


def normalize_result(result: LiveResult) -> dict[str, Any]:
    limitations: list[str] = []
    if result.canceled:
        return {
            "status": "canceled",
            "reason": "The run was canceled; the engine process group was terminated.",
            "limitations": ["Cancellation can leave partial artifacts; treat coverage as unknown."],
        }
    if result.timed_out:
        return {
            "status": "interrupted",
            "reason": "The engine exceeded its execution deadline and was terminated.",
            "limitations": ["The deadline stopped the scan; remaining scope was not reached."],
        }
    if result.launch_error:
        return {"status": "failed", "reason": result.launch_error, "limitations": []}
    if result.exit_code == EXIT_FATAL:
        limitations.append(
            "The engine exited with a fatal error; check the worker logs for the sanitized cause."
        )
        return {
            "status": "failed",
            "reason": "The engine reported a fatal error.",
            "limitations": limitations,
        }
    if result.exit_code not in {EXIT_NO_FINDINGS, EXIT_FINDINGS}:
        limitations.append(f"Unexpected engine exit code {result.exit_code}.")
        return {
            "status": "failed",
            "reason": "The engine exited with an unrecognised status.",
            "limitations": limitations,
        }
    if not result.artifacts_dir:
        limitations.append(
            "The engine exited without producing run artifacts; no findings are imported."
        )
    if not result.cleanup_confirmed:
        limitations.append(
            "Sandbox cleanup could not be confirmed; redispatch is blocked until an operator "
            "verifies the runtime is stopped."
        )
    if result.had_findings:
        limitations.append(
            "Exit code 2 means findings at or above the engine threshold were reported; it "
            "does not by itself establish coverage."
        )
    if result.raw_status == "stopped":
        limitations.append(
            "The engine stopped at its budget ceiling, so coverage is partial by definition."
        )
    return {"status": "completed", "reason": "", "limitations": limitations}


def live_result_row(result: LiveResult) -> dict[str, Any]:
    return {
        "exit_code": result.exit_code,
        "artifacts_dir": result.artifacts_dir,
        "timed_out": result.timed_out,
        "canceled": result.canceled,
        "cleanup_confirmed": result.cleanup_confirmed,
        "engine_status": result.raw_status,
        "duration_seconds": result.duration_seconds,
    }


def run_directory(artifact_root: Path, run_id: uuid.UUID) -> Path:
    path = artifact_root / "runs" / str(run_id)
    path.mkdir(parents=True, exist_ok=True)
    return path
