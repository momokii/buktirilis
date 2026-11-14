"""Strix adapter contract tests: argv, exit codes, artifact discovery, cancellation.

A local fake CLI stands in for the real engine, so these run without network, Docker,
or model credentials. Live execution against the real pinned release is unverified.
"""

from __future__ import annotations

import stat
from pathlib import Path

import pytest

from app.services.strix_adapter import (
    build_argv,
    find_artifacts_dir,
    live_preflight,
    normalize_result,
    run_live,
    write_instruction,
)

FAKE_STRIX = """#!/usr/bin/env python3
import json, os, sys, time
from pathlib import Path
args = sys.argv[1:]
if "--version" in args:
    print("strix 1.7.1")
    sys.exit(0)
mode_file = Path(__file__).with_name("fake-mode")
mode = mode_file.read_text().strip() if mode_file.exists() else "exit0"
if mode.startswith("sleep:"):
    time.sleep(float(mode.split(":", 1)[1]))
target = os.path.join(os.getcwd(), "strix_runs", "fake-run")
os.makedirs(os.path.join(target, "vulnerabilities"), exist_ok=True)
json.dump(
    {
        "run_id": "fake-run",
        "run_name": "fake-run",
        "status": "completed",
        "scan_mode": "quick",
        "targets_info": [{"target": "http://127.0.0.1"}],
        "llm_usage": {"cost": 0.01},
    },
    open(os.path.join(target, "run.json"), "w"),
)
json.dump([], open(os.path.join(target, "vulnerabilities.json"), "w"))
json.dump(
    {
        "schema_version": 1,
        "completeness": {"complete": True, "scan_status": "completed", "caveats": []},
        "entries": [],
        "gaps": [],
    },
    open(os.path.join(target, "coverage.json"), "w"),
)
open(os.path.join(target, "vulnerabilities", "vuln-1.md"), "w").write("# fake\\n")
print("fake engine finished")
sys.exit(int(mode.removeprefix("exit") or "0"))
"""


@pytest.fixture()
def fake_strix(tmp_path: Path) -> Path:
    path = tmp_path / "fake-strix"
    path.write_text(FAKE_STRIX, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return path


def set_mode(fake: Path, mode: str) -> None:
    fake.with_name("fake-mode").write_text(mode, encoding="utf-8")


def test_build_argv_is_structured_and_bounded(settings, tmp_path):
    instruction = write_instruction(
        tmp_path,
        profile_name="Web & API Access Control",
        approved_origins=["https://staging.example"],
    )
    argv = build_argv(
        settings,
        target_url="https://staging.example/api",
        depth="quick",
        budget_usd=1.5,
        max_turns=12,
        instruction_path=instruction,
        spec_path=tmp_path / "spec.json",
    )
    assert argv[0] == settings.strix_binary
    assert argv[1] == "-n"
    assert "--target" in argv and "https://staging.example/api" in argv
    assert "--scan-mode" in argv and "quick" in argv
    assert "--max-budget" in argv and "1.50" in argv
    assert "--max-turns" in argv and "12" in argv
    assert "--instruction-file" in argv
    assert argv[-2:] == ["--target", str(tmp_path / "spec.json")]
    assert "sh" not in argv and "-c" not in argv
    text = instruction.read_text().lower()
    assert "bearer" not in text and "lab." not in text


def test_live_preflight_reports_missing_model(settings, monkeypatch, fake_strix):
    from app.config import Settings

    local = Settings(
        APP_ENV="development",
        BUKTIRILIS_SECRET_KEY="test-only-secret-key-with-enough-length-1234",
        STRIX_BINARY=str(fake_strix),
        STRIX_MODEL="",
    )
    pre = live_preflight(local)
    codes = {check["code"]: check for check in pre.checks}
    assert codes["strix_binary"]["status"] == "pass"
    assert codes["model"]["status"] == "fail"
    assert pre.ok is False


def test_run_live_collects_artifacts_and_normalises_exit_two(
    settings, fake_strix, tmp_path, monkeypatch
):
    local = settings.model_copy(
        update={"strix_binary": str(fake_strix), "strix_model": "test/model"}
    )
    set_mode(fake_strix, "exit2")
    result = run_live(
        local,
        target_url="http://127.0.0.1:8099/deployments/2024.10.1",
        depth="quick",
        budget_usd=1.0,
        max_turns=5,
        approved_origins=["http://127.0.0.1:8099"],
        profile_name="Web & API Access Control",
        run_dir=tmp_path,
        spec_path=None,
        timeout_seconds=30,
        cancel_check=lambda: False,
    )
    assert result.exit_code == 2
    assert result.artifacts_dir
    assert find_artifacts_dir(tmp_path) == Path(result.artifacts_dir)
    normalized = normalize_result(result)
    assert normalized["status"] == "completed"
    assert any("Exit code 2" in limitation for limitation in normalized["limitations"])


def test_run_live_cancellation_terminates_the_process_group(
    settings, fake_strix, tmp_path, monkeypatch
):
    local = settings.model_copy(
        update={"strix_binary": str(fake_strix), "strix_model": "test/model"}
    )
    set_mode(fake_strix, "sleep:30")
    checks = {"count": 0}

    def cancel_check() -> bool:
        checks["count"] += 1
        return checks["count"] > 1

    result = run_live(
        local,
        target_url="http://127.0.0.1:8099/deployments/2024.10.1",
        depth="quick",
        budget_usd=1.0,
        max_turns=5,
        approved_origins=["http://127.0.0.1:8099"],
        profile_name="Web & API Access Control",
        run_dir=tmp_path,
        spec_path=None,
        timeout_seconds=30,
        cancel_check=cancel_check,
    )
    assert result.canceled is True
    assert result.cleanup_confirmed is True
    assert normalize_result(result)["status"] == "canceled"


def test_run_live_deadline_interrupts(settings, fake_strix, tmp_path, monkeypatch):
    local = settings.model_copy(
        update={"strix_binary": str(fake_strix), "strix_model": "test/model"}
    )
    set_mode(fake_strix, "sleep:30")
    result = run_live(
        local,
        target_url="http://127.0.0.1:8099/deployments/2024.10.1",
        depth="quick",
        budget_usd=1.0,
        max_turns=5,
        approved_origins=["http://127.0.0.1:8099"],
        profile_name="Web & API Access Control",
        run_dir=tmp_path,
        spec_path=None,
        timeout_seconds=1,
        cancel_check=lambda: False,
    )
    assert result.timed_out is True
    assert normalize_result(result)["status"] == "interrupted"


def test_launch_failure_is_actionable(settings, tmp_path):
    local = settings.model_copy(update={"strix_binary": str(tmp_path / "missing-binary")})
    result = run_live(
        local,
        target_url="http://127.0.0.1:8099/deployments/2024.10.1",
        depth="quick",
        budget_usd=1.0,
        max_turns=5,
        approved_origins=["http://127.0.0.1:8099"],
        profile_name="Web & API Access Control",
        run_dir=tmp_path,
        spec_path=None,
        timeout_seconds=10,
        cancel_check=lambda: False,
    )
    assert result.launch_error
    normalized = normalize_result(result)
    assert normalized["status"] == "failed"
    assert "could not be launched" in normalized["reason"]
