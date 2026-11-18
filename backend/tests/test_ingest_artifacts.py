"""Artifact loading contract tests, independent of a live engine."""

from __future__ import annotations

import json
from pathlib import Path

from app.services.ingest import load_artifact_bundle


def _write(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_clean_strix_sarif_is_not_a_missing_findings_index(tmp_path: Path) -> None:
    _write(tmp_path / "run.json", {"status": "completed"})
    _write(tmp_path / "coverage.json", {"summary": {"findings_filed": 0}})
    _write(
        tmp_path / "findings.sarif",
        {
            "version": "2.1.0",
            "runs": [
                {
                    "results": [
                        {"ruleId": "strix-coverage/auth", "kind": "pass"},
                        {"ruleId": "strix-coverage/idor", "kind": "pass"},
                    ]
                }
            ],
        },
    )
    bundle = load_artifact_bundle(tmp_path)
    assert "vulnerabilities.json" not in bundle.missing
    assert bundle.status == "complete"


def test_sarif_finding_keeps_the_missing_index_warning(tmp_path: Path) -> None:
    _write(tmp_path / "run.json", {"status": "completed"})
    _write(tmp_path / "coverage.json", {"summary": {"findings_filed": 1}})
    _write(
        tmp_path / "findings.sarif",
        {
            "version": "2.1.0",
            "runs": [{"results": [{"ruleId": "strix/bola-123", "level": "error"}]}],
        },
    )
    bundle = load_artifact_bundle(tmp_path)
    assert "vulnerabilities.json" in bundle.missing
    assert bundle.status == "partial"
