"""Verify known agent infrastructure; optional schema/native checks never start an AI run."""

import argparse
from fnmatch import fnmatchcase
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import tomllib
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parent.parent
FILES = [
    "AGENTS.md", "CLAUDE.md", "README.md", ".gitignore", ".env.example", "opencode.json",
    ".claude/settings.json", ".claude/README.md", ".claude/AGENT_RULES.md",
    ".claude/CODING_STANDARDS.md", ".claude/SECURITY_STANDARDS.md",
    ".claude/ENVIRONMENT_GUIDE.md", ".claude/HOW_TO_RESUME.md",
    ".claude/commands/resume.md", ".claude/commands/wrap-up.md",
    ".claude/commands/security-check.md", ".claude/state/CURRENT_STATUS.md",
    ".claude/state/TASK_QUEUE.md", ".claude/state/DECISIONS_LOG.md", ".claude/state/HISTORY.md",
    ".claude/templates/new_feature.md", ".claude/templates/new_endpoint.md",
    ".claude/templates/new_test.md", ".claude/templates/bug_fix.md",
    ".codex/config.toml", ".codex/rules/project.rules", ".agents/README.md",
    ".agents/skills/project-resume/SKILL.md", ".agents/skills/project-wrap-up/SKILL.md",
    ".agents/skills/project-security-check/SKILL.md", ".pi/extensions/project-policy.js",
    ".agents/tests/pi-policy.test.mjs", ".agents/tests/pi-native.mjs", ".agents/verify.py",
]
CONTEXT = ["CLAUDE.md", ".claude/AGENT_RULES.md", ".claude/CODING_STANDARDS.md",
           ".claude/SECURITY_STANDARDS.md", ".claude/state/CURRENT_STATUS.md"]


def run(command, cwd, env=None):
    result = subprocess.run(command, cwd=cwd, env=env, text=True, capture_output=True, timeout=60)
    # Native diagnostics run only against isolated, non-secret fixture configurations.
    if result.returncode:
        raise RuntimeError(f"Validation command failed: {command[0]}\n{result.stderr[:3000]}")
    return result.stdout


def static_checks():
    texts = {}
    for name in FILES:
        path = ROOT / name
        assert path.is_file() and not path.is_symlink(), name
        text = path.read_text(encoding="utf-8")
        assert text.strip() and text.endswith("\n"), name
        assert all(line == line.rstrip() for line in text.splitlines()), name
        texts[name] = text
    expected = [f"@{name}" for name in CONTEXT[1:]]
    assert re.findall(r"^@\S+$", texts["CLAUDE.md"], re.MULTILINE) == expected
    assert "```" not in texts["CLAUDE.md"] and "~~~" not in texts["CLAUDE.md"]
    for name, limit in [("AGENTS.md", 150), ("CLAUDE.md", 120),
                        *[(name, 150) for name in CONTEXT[1:-1]], (CONTEXT[-1], 80)]:
        assert len(texts[name].splitlines()) < limit, name
    for name in CONTEXT:
        assert f"`{name}`" in texts["AGENTS.md"], name
    claude = json.loads(texts[".claude/settings.json"])
    assert set(claude["permissions"]) == {"allow", "ask", "deny"}
    assert "defaultMode" not in texts[".claude/settings.json"]
    assert "Bash(*)" not in claude["permissions"]["allow"]
    for tool in ["Read", "Edit"]:
        assert f"{tool}(./.env)" in claude["permissions"]["deny"]
        assert f"{tool}(./.env.*)" not in claude["permissions"]["deny"]
        assert f"{tool}(./.env.example)" not in claude["permissions"]["deny"]
    opencode = json.loads(texts["opencode.json"])
    assert opencode["instructions"] == CONTEXT
    assert opencode["permission"]["bash"]["*"] == "ask"
    assert opencode["permission"]["edit"]["*"] == "ask"
    assert opencode["permission"]["read"]["*.env"] == "deny"
    codex = tomllib.loads(texts[".codex/config.toml"])
    assert codex["approval_policy"] == "on-request"
    assert codex["sandbox_mode"] == "workspace-write"
    assert codex["sandbox_workspace_write"]["network_access"] is False
    assert codex["shell_environment_policy"]["ignore_default_excludes"] is False
    for config in [opencode, codex]:
        assert "model" not in config and "provider" not in config and "model_provider" not in config
    for name in ["project-resume", "project-wrap-up", "project-security-check"]:
        skill = texts[f".agents/skills/{name}/SKILL.md"]
        assert skill.startswith(f"---\nname: {name}\ndescription: ")
        procedure = name.removeprefix("project-")
        assert f".claude/commands/{procedure}.md" in skill
        assert procedure in opencode["command"][name]["template"]
    for entry in [".env", ".env.*", "!.env.example", "CLAUDE.local.md",
                  ".claude/settings.local.json", "*.pem", "*.key", "secrets/"]:
        assert entry in texts[".gitignore"].splitlines()
    assert [line for line in texts[".env.example"].splitlines()
            if line and not line.startswith("#")] == ["APP_ENV=development"]
    # Personal configuration may legitimately exist; never open it during verification.
    hygiene = [r"-----BEGIN (?:[A-Z0-9]+ )*PRIVATE KEY-----", r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b",
               r"\bgh[pousr]_[A-Za-z0-9]{20,}\b", r"\bsk-(?:ant-)?[A-Za-z0-9_-]{24,}\b",
               r"/(?:home|Users|Volumes|mnt)/[A-Za-z0-9_.-]+",
               r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"]
    for name, text in texts.items():
        for pattern in hygiene:
            assert not re.search(pattern, text), f"Hygiene finding in {name}; value redacted"
    print(f"PASS: {len(FILES)} substantive files, four imports/budgets, shared entry points/workflows, JSON/TOML, targeted hygiene")
    return texts, opencode, codex


def schema_checks(opencode, codex, opencode_schema=None, codex_schema=None):
    import jsonschema  # Optional validation tooling; never installed by this script.
    for name, config, url, source in [
        ("OpenCode", opencode, "https://opencode.ai/config.json", opencode_schema),
        ("Codex", codex, "https://developers.openai.com/codex/config-schema.json", codex_schema),
    ]:
        if source:
            schema = json.loads(source.read_text(encoding="utf-8"))
        else:
            with urlopen(url, timeout=30) as response:
                schema = json.load(response)
        jsonschema.validate(config, schema)
        print(f"PASS: {name} configuration validates against {'provided' if source else 'live'} published schema")


def opencode_decision(config, action, resource):
    """Evaluate retained rules for fixtures only; native UI enforcement remains unverified."""
    if isinstance(config.get("permissions"), list):
        rules = config["permissions"]
        action = "shell" if action == "bash" else action
    else:
        permission = config["permission"]
        rules = []
        for tool, entries in permission.items():
            entries = entries if isinstance(entries, dict) else {"*": entries}
            rules.extend({"action": tool, "resource": pattern, "effect": effect}
                         for pattern, effect in entries.items())
    decision = "ask"
    for rule in rules:
        pattern = rule["resource"]
        matches = fnmatchcase(resource, pattern) or (pattern.endswith(" *") and resource == pattern[:-2])
        if fnmatchcase(action, rule["action"]) and matches:
            decision = rule["effect"]
    return decision


def fixture_checks(texts, native, pi_package):
    git = shutil.which("git")
    assert git, "Git is required to verify actual ignore behavior"
    with tempfile.TemporaryDirectory(prefix="agent-infra-") as temporary:
        base = Path(temporary)
        workspace = base / "workspace"
        workspace.mkdir()
        for name, text in texts.items():
            path = workspace / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        home = base / "home"
        home.mkdir()
        codex_home = home / ".codex"
        codex_home.mkdir()
        # Test-only trust of a synthetic fixture; no real user's trust/config is changed.
        (codex_home / "config.toml").write_text(
            f"[projects.{json.dumps(str(workspace))}]\ntrust_level = \"trusted\"\n", encoding="utf-8")
        env = {"PATH": os.environ.get("PATH", ""), "HOME": str(home),
               "XDG_CONFIG_HOME": str(home / ".config"), "XDG_DATA_HOME": str(home / ".data"),
               "XDG_STATE_HOME": str(home / ".state"), "XDG_CACHE_HOME": str(home / ".cache"),
               "CODEX_HOME": str(codex_home), "PI_OFFLINE": "1", "NO_COLOR": "1", "TMPDIR": str(base)}
        run([git, "-c", "init.defaultBranch=main", "init", "--quiet"], workspace, env)
        ignored = [".env", ".env.custom", "nested/.env.production", "CLAUDE.local.md",
                   ".claude/settings.local.json", "private.key", "private.pem", "secrets/fixture",
                   ".codex/auth.json", ".codex/sessions/fixture", ".pi/auth.json", ".pi/sessions/fixture"]
        visible = [".env.example", "nested/.env.example", "AGENTS.md", "opencode.json", ".codex/config.toml"]
        result = subprocess.run([git, "check-ignore", "--no-index", "--stdin"], cwd=workspace,
                                env=env, input="\n".join(ignored + visible) + "\n", text=True,
                                capture_output=True, check=True)
        assert set(result.stdout.splitlines()) == set(ignored)
        print(f"PASS: actual Git ignore behavior ({len(ignored)} private paths excluded; {len(visible)} shared paths visible)")
        if not native:
            return
        codex = shutil.which("codex")
        if codex:
            samples = [(["sudo", "true"], "forbidden"), (["git", "push", "--force", "origin", "main"], "forbidden"),
                       (["chmod", "-R", "777", "example"], "forbidden"), (["git", "push", "origin", "main"], "prompt"),
                       (["git", "push", "origin", "--force"], "prompt"), (["git", "clean", "-fd"], "prompt"),
                       (["docker", "compose", "up"], "prompt"), (["curl", "https://example.com"], "prompt")]
            for command, decision in samples:
                result = json.loads(run([codex, "execpolicy", "check", "--rules", ".codex/rules/project.rules", "--", *command], workspace, env))
                assert result["decision"] == decision, command
            print(f"PASS: installed Codex execpolicy evaluates {len(samples)} deny/prompt cases; no proposed command executed")
            prompt = run([codex, "debug", "prompt-input", "Validate instruction discovery only"], workspace, env)
            assert "Shared Project Instructions" in prompt and "Required context: load before work" in prompt
            print("PASS: installed Codex discovers AGENTS.md in an isolated prompt-input diagnostic (no model call)")
        else:
            print("UNVERIFIED: Codex CLI is not installed")
        opencode = shutil.which("opencode")
        if opencode:
            output = run([opencode, "debug", "config", "--pure"], workspace, env)
            resolved = json.loads(output)
            rendered = json.dumps(resolved)
            for source in CONTEXT:
                assert source in rendered, source
            assert "project-security-check" in rendered
            cases = [("read", ".env", "deny"), ("read", "nested/.env.production", "deny"),
                     ("read", ".env.example", "allow"), ("edit", ".env.example", "ask"),
                     ("edit", ".env.test", "deny"), ("bash", "sudo true", "deny"),
                     ("bash", "node --version", "ask"), ("bash", "docker compose up", "ask"),
                     ("bash", "git status", "allow")]
            for action, resource, expected in cases:
                assert opencode_decision(resolved, action, resource) == expected, (action, resource)
            print("PASS: installed OpenCode retains five instruction paths/workflows and native config rules satisfy nine deny/ask/allow fixtures")
        else:
            print("UNVERIFIED: OpenCode CLI is not installed")
        if pi_package:
            agent_dir = base / "pi-agent"
            agent_dir.mkdir()
            print(run([shutil.which("node") or "node", str(ROOT / ".agents/tests/pi-native.mjs"),
                       str(pi_package.resolve()), str(workspace), str(agent_dir)], workspace, env).strip())
        else:
            print("UNVERIFIED: pass --pi-package with an installed Pi package directory for native loader verification")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--schemas", action="store_true", help="Validate using current official schemas (network + jsonschema required)")
    parser.add_argument("--native", action="store_true", help="Run installed CLI/loader diagnostics in an isolated fixture, without AI requests")
    parser.add_argument("--pi-package", type=Path, help="Installed Pi coding-agent package directory for its native loader test")
    parser.add_argument("--opencode-schema", type=Path, help="Previously retrieved official OpenCode schema (avoids downloading)")
    parser.add_argument("--codex-schema", type=Path, help="Previously retrieved official Codex schema (avoids downloading)")
    args = parser.parse_args()
    texts, opencode, codex = static_checks()
    fixture_checks(texts, args.native, args.pi_package)
    if args.schemas:
        schema_checks(opencode, codex, args.opencode_schema, args.codex_schema)
    print("LIMITS: interactive trust/approvals and model behavior require host acceptance; dedicated secret scan not performed")


if __name__ == "__main__":
    main()
