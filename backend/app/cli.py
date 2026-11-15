"""Operator CLI: bootstrap, demo seed, migrations, and safe local checks."""

from __future__ import annotations

import argparse
import getpass
import os
import sys
from pathlib import Path

from sqlalchemy import select, text

from app.config import get_settings
from app.db import session_scope
from app.models import Finding, Project, Run, User
from app.security import hash_password
from app.services.lab_seed import credentials_file, seed_demo, sync_profiles


def _fail(message: str) -> int:
    print(f"error: {message}", file=sys.stderr)
    return 1


def _read_password(args) -> str:
    if getattr(args, "password_env", None):
        value = os.environ.get(args.password_env, "")
        if not value:
            raise SystemExit(f"error: environment variable {args.password_env} is empty")
        return value
    if sys.stdin.isatty():
        first = getpass.getpass("Admin password: ")
        second = getpass.getpass("Repeat password: ")
        if first != second:
            raise SystemExit("error: passwords did not match")
        return first
    value = sys.stdin.readline().strip()
    if not value:
        raise SystemExit("error: no password received on stdin")
    return value


def cmd_bootstrap_admin(args) -> int:
    settings = get_settings()
    password = _read_password(args)
    email = args.email.strip().lower()
    with session_scope() as db:
        if db.execute(select(User).where(User.email == email)).scalar_one_or_none():
            return _fail(f"an account already exists for {email}")
        user = User(
            email=email,
            display_name=args.name.strip(),
            password_hash=hash_password(password),
            is_admin=True,
            is_active=True,
        )
        db.add(user)
        db.flush()
        print(f"created administrator {user.email} ({user.id})")
    print(f"APP_ENV={settings.app_env}: sign in through the web app to create the first project.")
    return 0


def cmd_seed_demo(args) -> int:
    settings = get_settings()
    if not settings.demo_enabled:
        return _fail(
            "demo seeding is disabled. Set APP_ENV=development (or DEMO_SEED_ENABLED=true) "
            "and retry."
        )
    path = Path(args.credentials_file).resolve() if args.credentials_file else credentials_file()
    with session_scope() as db:
        try:
            result = seed_demo(
                db,
                settings=settings,
                admin_email=args.admin_email,
                credentials_path=path,
            )
        except RuntimeError as exc:
            return _fail(str(exc))
    if result.get("already_seeded"):
        print(f"demo already seeded: project {result['project_id']}")
        return 0
    print("demo dataset created (synthetic; labelled as Demo in the UI and exports)")
    print(f"  project: {result['project_slug']} ({result['project_id']})")
    print(f"  builds:  {', '.join(result['builds'])}")
    print("  runs:    baseline, patched, regressed")
    if result["credentials_written"]:
        print(f"  demo credentials written to {path} (gitignored, mode 600)")
    else:
        print("  no new passwords were written; existing demo accounts were reused")
    print(
        "  note: the deliberate identity-mismatch build is "
        f"{result['variants']['identity_mismatch_build']}"
    )
    return 0


def cmd_reset_password(args) -> int:
    password = _read_password(args)
    email = args.email.strip().lower()
    with session_scope() as db:
        user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
        if user is None:
            return _fail(f"no account exists for {email}")
        user.password_hash = hash_password(password)
        from app.models import UserSession

        revoked = (
            db.query(UserSession)
            .filter(UserSession.user_id == user.id, UserSession.revoked_at.is_(None))
            .update(
                {
                    UserSession.revoked_at: __import__("datetime").datetime.now(
                        __import__("datetime").UTC
                    )
                }
            )
        )
        db.flush()
    print(f"password reset for {email}; {revoked} active session(s) revoked")
    return 0


def cmd_profiles(args) -> int:
    with session_scope() as db:
        sync_profiles(db)
    print("profile registry synchronised")
    return 0


def cmd_upgrade(args) -> int:
    from alembic import command
    from alembic.config import Config

    root = Path(__file__).resolve().parents[1]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "migrations"))
    command.upgrade(config, args.revision or "head")
    print("database migrated to head")
    return 0


def cmd_check(args) -> int:
    settings = get_settings()
    with session_scope() as db:
        db.execute(text("select 1"))
        users = db.execute(select(User.email)).scalars().all()
        projects = db.execute(select(Project.slug)).scalars().all()
        runs = db.execute(select(Run.status, Run.id)).all()
        findings = db.execute(select(Finding.public_id)).scalars().all()
    print(f"app_env={settings.app_env} demo={settings.demo_enabled} live={settings.live_enabled}")
    print(f"users={len(users)} projects={len(projects)} runs={len(runs)} findings={len(findings)}")
    if not users:
        print("next: python -m app.cli bootstrap-admin --email you@example.com")
    elif not projects:
        print("next: python -m app.cli seed-demo")
    else:
        print("next: start the API, worker, web app, and lab; see README.md")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    subs = parser.add_subparsers(dest="command", required=True)

    bootstrap = subs.add_parser("bootstrap-admin", help="create the first administrator")
    bootstrap.add_argument("--email", required=True)
    bootstrap.add_argument("--name", default="Installation Admin")
    bootstrap.add_argument(
        "--password-env",
        default="",
        help="read the password from this environment variable instead of stdin",
    )
    bootstrap.set_defaults(func=cmd_bootstrap_admin)

    reset = subs.add_parser("reset-password", help="reset an account password (break-glass)")
    reset.add_argument("--email", required=True)
    reset.add_argument(
        "--password-env",
        default="",
        help="read the password from this environment variable instead of stdin",
    )
    reset.set_defaults(func=cmd_reset_password)

    seed = subs.add_parser("seed-demo", help="create the synthetic demo dataset")
    seed.add_argument("--admin-email", default=None)
    seed.add_argument("--credentials-file", default=None)
    seed.set_defaults(func=cmd_seed_demo)

    profiles = subs.add_parser("sync-profiles", help="synchronise the profile registry")
    profiles.set_defaults(func=cmd_profiles)

    upgrade = subs.add_parser("upgrade", help="apply database migrations")
    upgrade.add_argument("--revision", default="head")
    upgrade.set_defaults(func=cmd_upgrade)

    check = subs.add_parser("check", help="show installation state")
    check.set_defaults(func=cmd_check)

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
