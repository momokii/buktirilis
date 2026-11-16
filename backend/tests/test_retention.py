"""Evidence retention keeps verdicts and frozen exports while pruning raw captures."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.models import Artifact, AuditEvent, Evidence
from app.services.evidence import create_evidence, save_bytes
from app.services.retention import prune_evidence
from tests.helpers import make_finding


def test_prune_evidence_removes_old_captures_but_keeps_metadata(db, lab_project):
    finding = make_finding(db, lab_project.project)
    artifact = save_bytes(
        db,
        project=lab_project.project,
        content=b'{"tenant_id":"tenant-a"}',
        filename="capture.json",
        content_type="application/json",
        created_by=lab_project.operator.id,
    )
    evidence = create_evidence(
        db,
        project=lab_project.project,
        finding_id=finding.id,
        run_id=None,
        attempt_id=None,
        build_id=lab_project.builds["2024.10.1"].id,
        kind="http_exchange",
        attribution="observed_capture",
        summary="Old capture",
        payload={"response": {"status": 200, "body": '{"tenant_id":"tenant-a"}'}},
        artifact_id=artifact.id,
        created_by=lab_project.operator.id,
    )
    evidence.created_at = datetime.now(UTC) - timedelta(days=90)
    db.commit()
    from app.services.evidence import artifact_root

    path = artifact_root() / str(lab_project.project.id) / str(artifact.id)
    assert path.is_file()

    dry = prune_evidence(db, days=30, dry_run=True)
    db.commit()
    assert dry["candidates"] == 1 and dry["pruned"] == 0
    assert path.is_file()

    result = prune_evidence(db, days=30)
    db.commit()
    db.refresh(evidence)
    assert result["pruned"] == 1
    assert result["artifacts_removed"] == 1
    assert evidence.pruned_at is not None
    assert evidence.artifact_id is None
    assert evidence.payload.get("pruned") is True
    assert not path.exists()
    assert db.get(Artifact, artifact.id) is None
    assert db.query(AuditEvent).filter_by(action="evidence.pruned").count() == 1
    assert db.query(Evidence).filter_by(id=evidence.id).count() == 1
