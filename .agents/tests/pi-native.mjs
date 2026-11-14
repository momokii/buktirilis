import assert from "node:assert/strict";
import { join } from "node:path";
import { pathToFileURL } from "node:url";

// Exercise the installed host's loaders without starting an agent or model request.
const [packageRoot, workspace, agentDir] = process.argv.slice(2);
assert.ok(packageRoot && workspace && agentDir, "Provide package, workspace, and empty agent directory");
const loader = await import(pathToFileURL(join(packageRoot, "dist/core/extensions/loader.js")).href);
const resources = await import(pathToFileURL(join(packageRoot, "dist/core/resource-loader.js")).href);
const context = resources.loadProjectContextFiles({ cwd: workspace, agentDir });
assert.ok(context.some((file) => file.path === join(workspace, "AGENTS.md")));
const extensionPath = join(workspace, ".pi/extensions/project-policy.js");
const result = await loader.loadExtensions([extensionPath], workspace);
assert.deepEqual(result.errors, [], "Pi reported an extension load error");
assert.equal(result.extensions.length, 1);
for (const name of ["session_start", "before_agent_start", "tool_call"]) {
  assert.ok(result.extensions[0].handlers.has(name), `Missing Pi handler: ${name}`);
}
console.log("PASS: installed Pi discovers AGENTS.md and loads the project extension with all three hooks");
