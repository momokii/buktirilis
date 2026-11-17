import { lstatSync, readFileSync, realpathSync, statSync } from "node:fs";
import { homedir } from "node:os";
import { basename, dirname, isAbsolute, join, relative, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";

export const CONTEXT_FILES = [
  "CLAUDE.md",
  ".claude/AGENT_RULES.md",
  ".claude/CODING_STANDARDS.md",
  ".claude/SECURITY_STANDARDS.md",
  ".claude/state/CURRENT_STATUS.md",
];

/** Resolve symlinks, including an existing ancestor of a new write destination. */
export function resolvePolicyPath(input, cwd) {
  if (typeof input !== "string" || !input.trim() || input.includes("\0")) {
    throw new Error("A valid explicit path is required");
  }
  const expanded = input === "~" ? homedir()
    : input.startsWith("~/") ? join(homedir(), input.slice(2)) : input;
  const requested = resolve(cwd, expanded);
  let ancestor = requested;
  const missing = [];
  while (true) {
    try {
      return { requested, canonical: join(realpathSync(ancestor), ...missing) };
    } catch (error) {
      // A dangling symlink or inaccessible path must not be treated as a new file.
      if (error.code !== "ENOENT" || dirname(ancestor) === ancestor) throw error;
      // An existing entry with no realpath is unsafe (for example a dangling link).
      if (lstatSync(ancestor, { throwIfNoEntry: false })) throw new Error("Path cannot be safely resolved");
      missing.unshift(basename(ancestor));
      ancestor = dirname(ancestor);
    }
  }
}

/** Identify protected names without opening their contents. */
export function isSensitivePath(path) {
  const parts = path.replaceAll("\\", "/").toLowerCase().split("/");
  const name = parts.at(-1);
  return parts.some((part) => ["secrets", ".ssh", ".aws"].includes(part))
    || name === ".env" || (name.startsWith(".env.") && name !== ".env.example")
    || /\.(pem|key|p12|pfx)$/.test(name)
    || (name === "settings.local.json" && parts.at(-2) === ".claude")
    || (name === "auth.json" && parts.some((part) => [".codex", ".pi"].includes(part)));
}

function isWithin(root, path) {
  const suffix = relative(root, path);
  return suffix === "" || (!isAbsolute(suffix) && suffix !== ".." && !suffix.startsWith(`..${sep}`));
}

/** Load only the fixed, versioned policy sources; reject external/secret symlink targets. */
export function loadProjectContext(root) {
  const canonicalRoot = realpathSync(root);
  return CONTEXT_FILES.map((name) => {
    const { canonical } = resolvePolicyPath(name, canonicalRoot);
    if (!isWithin(canonicalRoot, canonical) || isSensitivePath(canonical)) {
      throw new Error(`Unsafe project context source: ${name}`);
    }
    const stat = statSync(canonical);
    if (!stat.isFile() || stat.size > 65536) throw new Error(`Invalid context source: ${name}`);
    const content = readFileSync(canonical, "utf8");
    if (!content.trim()) throw new Error(`Empty context source: ${name}`);
    return `## Project source: ${name}\n${content}`;
  }).join("\n\n");
}

/** Direct safe project reads are automatic; every other operation needs approval. */
export function classifyToolCall(event, cwd, root) {
  if (["bash", "powershell"].includes(event.toolName)) {
    const command = event.input?.command;
    if (typeof command !== "string") return "deny";
    // Best-effort direct-form rejects only; all other shell forms still require review.
    if (/^\s*(sudo\b|chmod\s+(-R\s+)?777\b)/.test(command)
      || /\bgit\s+push\b[^\n]*(\s--force\S*|\s-f)(\s|$)/.test(command)) return "deny";
  }
  if (["read", "edit", "write"].includes(event.toolName)) {
    try {
      const paths = resolvePolicyPath(event.input?.path, cwd);
      if (isSensitivePath(paths.requested) || isSensitivePath(paths.canonical)) return "deny";
      if (event.toolName === "read" && isWithin(realpathSync(root), paths.canonical)) return "allow";
    } catch {
      return "deny";
    }
  }
  return "ask";
}

/** Global auto-approve switch: any project using this extension honours the same flag file. */
export const AUTO_APPROVE_FLAG = join(homedir(), ".pi/agent/project-policy-auto-approve");

export function autoApproveEnabled() {
  try {
    return readFileSync(AUTO_APPROVE_FLAG, "utf8").trim() === "all";
  } catch {
    return false;
  }
}

/** Gate an operation; missing UI, rejected prompts, or prompt failures deny execution. */
export async function gateToolCall(event, ctx, root) {
  const decision = classifyToolCall(event, ctx.cwd, root);
  if (decision === "allow") return;
  const blocked = { block: true, reason: "Project policy refused this operation; do not work around it." };
  // Hard denies are never bypassed, even in auto-approve mode.
  if (decision === "deny") return blocked;
  // "ask" is auto-approved only while the global flag file says so; read per call so it
  // takes effect without restarting a session.
  if (autoApproveEnabled()) return;
  if (!ctx.hasUI) return blocked;
  try {
    const detail = JSON.stringify(event.input ?? {});
    if (await ctx.ui.confirm(`Approve project tool: ${event.toolName}`, detail)) return;
  } catch {
    // Approval failure is denial, not permission to continue.
  }
  return blocked;
}

/** Pi extension: inject current shared policy each run and gate tool execution. */
export default function projectPolicy(pi) {
  const root = realpathSync(fileURLToPath(new URL("../../", import.meta.url)));
  let contextReady = false;
  pi.on("session_start", async (_event, ctx) => {
    contextReady = false;
    if (ctx.hasUI) {
      const state = autoApproveEnabled() ? "auto-approve" : "approvals required";
      ctx.ui.setStatus("project-policy", `project policy active; ${state}`);
    }
  });
  pi.on("before_agent_start", async (event, ctx) => {
    contextReady = false;
    try {
      if (!isWithin(root, realpathSync(ctx.cwd))) throw new Error("Wrong project");
      const context = loadProjectContext(root);
      contextReady = true;
      return { systemPrompt: `${event.systemPrompt}\n\n${context}` };
    } catch {
      return { systemPrompt: `${event.systemPrompt}\n\nPROJECT POLICY LOAD FAILED. All tools are blocked. Report the missing/unsafe project context; do not attempt implementation.` };
    }
  });
  pi.on("tool_call", async (event, ctx) => {
    if (!contextReady) return { block: true, reason: "Required project context is not loaded." };
    return gateToolCall(event, ctx, root);
  });
}
