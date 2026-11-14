"""Shared test fixtures.

The suite runs against an isolated PostgreSQL database and a real local lab HTTP
server, so automatic retest tests exercise the constrained runner over the network.
"""

from __future__ import annotations

import importlib.util
import os
import socket
import sys
import threading
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

BACKEND_ROOT = Path(__file__).resolve().parents[1]
LAB_ROOT = Path(__file__).resolve().parents[2] / "lab"
sys.path.insert(0, str(BACKEND_ROOT))

os.environ.setdefault("APP_ENV", "development")
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://buktirilis:buktirilis-dev-only@127.0.0.1:55432/buktirilis_test",
)
os.environ.setdefault("BUKTIRILIS_SECRET_KEY", "test-only-secret-key-with-enough-length-1234")
os.environ.setdefault("ARTIFACT_ROOT", str(Path("/tmp/buktirilis-test-artifacts")))
os.environ.setdefault("STRIX_RUNS_ROOT", str(Path("/tmp/buktirilis-test-runs")))
os.environ.setdefault("ALLOW_LOOPBACK_LAB_TARGETS", "true")
os.environ.setdefault("DEMO_SEED_ENABLED", "true")
os.environ.setdefault("LIVE_EXECUTION_ENABLED", "false")
os.environ.setdefault("LAB_BASE_URL", "http://127.0.0.1:18099")

from app.config import get_settings  # noqa: E402
from app.db import configure_engine  # noqa: E402
from app.models import Base  # noqa: E402


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.fixture(scope="session")
def lab_server():
    """Start the synthetic lab app on a loopback port for real replay tests."""
    import uvicorn

    spec = importlib.util.spec_from_file_location("lab_main", LAB_ROOT / "app" / "main.py")
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    port = int(os.environ["LAB_BASE_URL"].rsplit(":", 1)[1])
    config = uvicorn.Config(module.APP, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    for _ in range(100):
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                break
        except OSError:
            time.sleep(0.05)
    else:  # pragma: no cover - defensive
        raise RuntimeError("lab server did not start")
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join(timeout=5)


@pytest.fixture(scope="session")
def engine():
    settings = get_settings()
    configure_engine(settings.database_url)
    from app.db import get_engine

    eng = get_engine()
    with eng.begin() as connection:
        connection.execute(text("DROP SCHEMA public CASCADE"))
        connection.execute(text("CREATE SCHEMA public"))
        Base.metadata.create_all(connection)
    yield eng
    with eng.begin() as connection:
        connection.execute(text("DROP SCHEMA public CASCADE"))
        connection.execute(text("CREATE SCHEMA public"))
    eng.dispose()


@pytest.fixture()
def db(engine) -> Session:
    factory = sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
    session = factory()
    with engine.begin() as connection:
        tables = ", ".join(f'"{name}"' for name in Base.metadata.tables)
        connection.execute(text(f"TRUNCATE {tables} CASCADE"))
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture()
def settings():
    return get_settings()


@pytest.fixture()
def client(engine) -> TestClient:
    from app.main import app

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def admin_client(client: TestClient):
    response = client.post(
        "/api/auth/bootstrap",
        json={
            "email": "admin@example.test",
            "display_name": "Test Admin",
            "password": "correct horse battery staple",
        },
    )
    assert response.status_code == 201, response.text
    csrf = client.get("/api/auth/session").json()["csrf_token"]
    client.headers.update({"X-CSRF-Token": csrf})
    return client


def make_lab_project(db: Session, *, lab_base: str, admin, operator=None, developer=None):
    """Create the demo project, builds, and accounts used by integration tests."""
    from app.models import Build, Project, ProjectMember, TargetConfig, TestAccount, User
    from app.security import encrypt_secret

    project = Project(slug="atlas-test", name="Atlas Test", created_by=admin.id)
    db.add(project)
    db.flush()
    config = TargetConfig(
        project_id=project.id,
        revision=1,
        base_url=lab_base,
        allowed_origins=[lab_base],
        path_prefixes=["/deployments"],
        environment_label="staging",
        scope_owner="Test Team",
        authorization_reference="TEST-AUTH-1",
        run_limits={"max_depth": "standard", "max_runs_per_day": 20, "max_replay_checks": 8},
        created_by=admin.id,
    )
    db.add(config)
    db.flush()
    for name, role, tenant in [
        ("tenant-a-owner", "owner", "tenant-a"),
        ("tenant-b-dev", "developer", "tenant-b"),
        ("tenant-b-expired", "developer", "tenant-b"),
        ("tenant-c-observer", "viewer", "tenant-c"),
    ]:
        db.add(
            TestAccount(
                project_id=project.id,
                name=name,
                role_label=role,
                tenant_label=tenant,
                credential_ciphertext=encrypt_secret(f"lab.{name}"),
                created_by=admin.id,
            )
        )
    builds = {}
    for label in ("2024.10.1", "2024.10.2", "2024.10.3"):
        build = Build(
            project_id=project.id,
            label=label,
            target_url=f"{lab_base}/deployments/{label}",
            target_config_id=config.id,
            expected_identity=label,
            build_metadata={"synthetic": True},
            created_by=admin.id,
        )
        db.add(build)
        builds[label] = build
    for user, role in ((operator, "operator"), (developer, "developer")):
        if user is not None:
            db.add(
                ProjectMember(
                    project_id=project.id, user_id=user.id, role=role, added_by=admin.id
                )
            )
    db.commit()
    return project, config, builds


@pytest.fixture()
def lab_project(db: Session, lab_server: str):
    """Demo-shaped project with builds and identities on the live lab server."""
    from types import SimpleNamespace

    from app.models import ProjectMember, User
    from app.security import hash_password

    admin = User(
        email="seed-admin@example.test",
        display_name="Seed Admin",
        password_hash=hash_password("correct horse battery staple"),
        is_admin=True,
        is_active=True,
    )
    operator = User(
        email="seed-operator@example.test",
        display_name="Seed Operator",
        password_hash=hash_password("correct horse battery staple"),
        is_active=True,
    )
    developer = User(
        email="seed-developer@example.test",
        display_name="Seed Developer",
        password_hash=hash_password("correct horse battery staple"),
        is_active=True,
    )
    viewer = User(
        email="seed-viewer@example.test",
        display_name="Seed Viewer",
        password_hash=hash_password("correct horse battery staple"),
        is_active=True,
    )
    db.add_all([admin, operator, developer, viewer])
    db.flush()
    project, config, builds = make_lab_project(
        db, lab_base=lab_server, admin=admin, operator=operator, developer=developer
    )
    db.add(ProjectMember(project_id=project.id, user_id=viewer.id, role="viewer", added_by=admin.id))
    db.commit()
    return SimpleNamespace(
        admin=admin,
        operator=operator,
        developer=developer,
        viewer=viewer,
        project=project,
        config=config,
        builds=builds,
        lab_base=lab_server,
    )
