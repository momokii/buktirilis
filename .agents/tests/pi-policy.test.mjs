import assert from "node:assert/strict";
import { mkdtempSync, mkdirSync, rmSync, symlinkSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";
import install, {
  classifyToolCall, CONTEXT_FILES, gateToolCall, isSensitivePath,
  loadProjectContext, resolvePolicyPath,
} from "../../.pi/extensions/project-policy.js";

const project = fileURLToPath(new URL("../../", import.meta.url));
const call = (toolName, input) => ({ toolName, input });

function fixture(t) {
  const directory = mkdtempSync(join(tmpdir(), "project-policy-test-"));
  t.after(() => rmSync(directory, { recursive: true, force: true }));
  return directory;
}

test("secret stores and environment variants are denied, while examples stay usable", () => {
  for (const path of [".env", "x/.env.new", "x/.env.production.local", "secrets/x",
    "x/private.key", "x/private.pem", "x/private.pfx", ".ssh/config", ".aws/config",
    ".claude/settings.local.json", ".codex/auth.json", ".pi/agent/auth.json"]) {
    assert.equal(isSensitivePath(path), true, path);
  }
  for (const path of [".env.example", "x/.env.example", "CLAUDE.md", ".codex/config.toml"]) {
    assert.equal(isSensitivePath(path), false, path);
  }
});

test("only safe direct reads within the project skip approval", (t) => {
  const root = fixture(t);
  writeFileSync(join(root, "public.md"), "Public fixture");
  assert.equal(classifyToolCall(call("read", { path: "public.md" }), root, root), "allow");
  for (const tool of ["edit", "write", "grep", "find", "ls", "custom_tool"]) {
    assert.equal(classifyToolCall(call(tool, { path: "public.md" }), root, root), "ask");
  }
  assert.equal(classifyToolCall(call("read", { path: "../outside.md" }), root, root), "ask");
});

test("secret reads and writes are blocked before prompting", async (t) => {
  const root = fixture(t);
  const ctx = { cwd: root, hasUI: true, ui: { confirm() { assert.fail("Must not prompt"); } } };
  for (const tool of ["read", "edit", "write"]) {
    const result = await gateToolCall(call(tool, { path: ".env.production" }), ctx, root);
    assert.equal(result.block, true);
  }
});

test("path traversal and a symlink into a secret store cannot disguise a read", (t) => {
  const root = fixture(t);
  mkdirSync(join(root, "secrets"));
  writeFileSync(join(root, "secrets", "fixture"), "Synthetic test placeholder");
  symlinkSync(join(root, "secrets", "fixture"), join(root, "public.md"));
  assert.equal(classifyToolCall(call("read", { path: "public.md" }), root, root), "deny");
  assert.equal(classifyToolCall(call("read", { path: "x/../.env" }), root, root), "deny");
});

test("new write destinations resolve through symlinked parent directories", (t) => {
  const root = fixture(t);
  mkdirSync(join(root, "secrets"));
  symlinkSync(join(root, "secrets"), join(root, "public"), "dir");
  assert.equal(classifyToolCall(call("write", { path: "public/new.txt" }), root, root), "deny");
  assert.equal(resolvePolicyPath("new/file.md", root).canonical, join(root, "new/file.md"));
});

test("dangling symlinks and malformed paths fail closed", (t) => {
  const root = fixture(t);
  symlinkSync(join(root, ".env.missing"), join(root, "public.md"));
  for (const path of ["public.md", "", "\0", null]) {
    assert.equal(classifyToolCall(call("read", { path }), root, root), "deny");
  }
});

test("shell commands require review and direct prohibited forms are denied", (t) => {
  const root = fixture(t);
  for (const command of ["node --version", "git status", "python script.py", "/usr/bin/curl https://example.com"]) {
    assert.equal(classifyToolCall(call("bash", { command }), root, root), "ask");
  }
  for (const command of ["sudo true", "chmod -R 777 example", "git push --force origin main",
    "git push origin main --force", "git push --force-with-lease origin main", "git push origin -f main"]) {
    assert.equal(classifyToolCall(call("bash", { command }), root, root), "deny");
  }
});

test("headless operation cannot implicitly approve shell, mutation, or unknown tools", async (t) => {
  const root = fixture(t);
  const ctx = { cwd: root, hasUI: false };
  for (const event of [call("bash", { command: "node --version" }),
    call("write", { path: "public.md" }), call("custom_tool", {})]) {
    assert.equal((await gateToolCall(event, ctx, root)).block, true);
  }
});

test("approval is per call and rejection or UI failure blocks execution", async (t) => {
  const root = fixture(t);
  const event = call("write", { path: "public.md" });
  let prompts = 0;
  const ctx = { cwd: root, hasUI: true, ui: { async confirm() { prompts++; return true; } } };
  assert.equal(await gateToolCall(event, ctx, root), undefined);
  assert.equal(await gateToolCall(event, ctx, root), undefined);
  assert.equal(prompts, 2);
  ctx.ui.confirm = async () => false;
  assert.equal((await gateToolCall(event, ctx, root)).block, true);
  ctx.ui.confirm = async () => { throw new Error("Test UI failure"); };
  assert.equal((await gateToolCall(event, ctx, root)).block, true);
});

test("context injection reads the five fixed sources in full and refreshes state", (t) => {
  const root = fixture(t);
  for (const name of CONTEXT_FILES) {
    mkdirSync(dirname(join(root, name)), { recursive: true });
    writeFileSync(join(root, name), `Synthetic policy for ${name}`);
  }
  assert.equal((loadProjectContext(root).match(/## Project source:/g) ?? []).length, 5);
  writeFileSync(join(root, CONTEXT_FILES.at(-1)), "Updated synthetic state");
  assert.ok(loadProjectContext(root).includes("Updated synthetic state"));
  rmSync(join(root, CONTEXT_FILES[0]));
  assert.throws(() => loadProjectContext(root));
});

test("context injection refuses external or secret symlink targets", (t) => {
  const root = fixture(t);
  const external = fixture(t);
  writeFileSync(join(external, "public.md"), "Synthetic external policy");
  symlinkSync(join(external, "public.md"), join(root, "CLAUDE.md"));
  assert.throws(() => loadProjectContext(root), /Unsafe project context/);
});

test("extension blocks tools until shared context is loaded and after a wrong-project run", async () => {
  const handlers = new Map();
  install({ on(name, handler) { handlers.set(name, handler); } });
  const ctx = { cwd: project, hasUI: false };
  const event = call("read", { path: "CLAUDE.md" });
  assert.equal((await handlers.get("tool_call")(event, ctx)).block, true);
  const response = await handlers.get("before_agent_start")({ systemPrompt: "Existing host instructions" }, ctx);
  assert.ok(response.systemPrompt.startsWith("Existing host instructions"));
  for (const name of CONTEXT_FILES) assert.ok(response.systemPrompt.includes(`## Project source: ${name}`));
  assert.equal(await handlers.get("tool_call")(event, ctx), undefined);
  await handlers.get("before_agent_start")({ systemPrompt: "Existing host instructions" }, { cwd: tmpdir() });
  assert.equal((await handlers.get("tool_call")(event, ctx)).block, true);
});
