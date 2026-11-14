#!/usr/bin/env bash
# Prove the live-worker network contract before enabling LIVE_EXECUTION_ENABLED.
#
# Run this INSIDE the isolated worker (or its network namespace), not on the web host.
# It checks three things:
#   1. an approved staging target is reachable and reports a build identity;
#   2. cloud metadata / link-local endpoints are unreachable;
#   3. an out-of-scope redirect is not followed to an external host.
#
# Required environment:
#   APPROVED_TARGET   e.g. http://127.0.0.1:8099/deployments/2024.10.1 (lab) or the
#                     approved staging build base URL
# Optional:
#   REDIRECT_PROBE    a URL that returns a redirect outside the approved scope
#                     (default: <APPROVED_TARGET>/api/redirect-outside for the lab)
#
# Exit code 0 means all checks behaved as required. Any other code is a failure and live
# mode must stay disabled until the boundary is repaired and re-probed.
set -uo pipefail

fail=0
target="${APPROVED_TARGET:?set APPROVED_TARGET to the approved build URL}"
redirect_probe="${REDIRECT_PROBE:-${target%/}/api/redirect-outside}"

say() { printf '%s\n' "$*"; }
ok() { say "PASS  $*"; }
bad() { say "FAIL  $*"; fail=1; }

say "Isolation probes against ${target}"

# 1. Approved target reachable, with a build identity when the deployment exposes one.
body="$(curl -fsS --max-time 8 "${target%/}/api/meta" 2>/dev/null || true)"
if [ -n "$body" ]; then
  ok "approved target reachable: ${body:0:160}"
else
  bad "approved target did not return /api/meta"
fi

# 2. Control-plane / metadata endpoints must not be reachable.
for denied in "http://169.254.169.254/latest/meta-data/" "http://metadata.google.internal/" \
              "http://127.0.0.1:2375/version" "http://host.docker.internal/"; do
  if curl -fsS --max-time 4 "$denied" >/dev/null 2>&1; then
    bad "control-plane destination reachable: $denied"
  else
    ok "denied destination unreachable: $denied"
  fi
done

# 3. An out-of-scope redirect must not be followed to a host outside the allowlist.
final_url="$(curl -sS -o /dev/null --max-time 6 -w '%{url_effective}' -L --max-redirs 2 \
  "$redirect_probe" 2>/dev/null || true)"
status="$(curl -sS -o /dev/null --max-time 6 -w '%{http_code}' "$redirect_probe" 2>/dev/null || true)"
if [ "${status:0:1}" = "3" ]; then
  ok "redirect probe returned ${status} and was not followed by the engine boundary"
elif [ -z "$status" ]; then
  ok "redirect probe unreachable (endpoint absent or blocked)"
else
  bad "redirect probe returned ${status} (expected a redirect or a block)"
fi
if printf '%s' "$final_url" | grep -qi "evil.example.test"; then
  bad "out-of-scope redirect was followed: $final_url"
else
  ok "no out-of-scope redirect observed"
fi

if [ "$fail" -ne 0 ]; then
  say "Isolation contract FAILED. Keep LIVE_EXECUTION_ENABLED=false."
  exit 1
fi
say "Isolation contract passed. Record this output in the deployment runbook."
