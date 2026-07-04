#!/bin/bash
# Autonomous Jarvis improver — drains one Claude quota batch per invocation.
#
# Intended to run from cron every 5 hours (aligned to Claude limit resets):
#   0 */5 * * * /home/azureuser/jarvis/scripts/improve-jarvis.sh
#
# Each claude -p call does exactly ONE roadmap step and opens a PR (never
# merges). The loop exits when claude fails — usually the quota running dry —
# and cron re-fires after the next reset.
#
# SAFETY: this uses --dangerously-skip-permissions. Only run it on a
# disposable, isolated VM. Never on your workstation.
set -u

# Single-instance lock: two loops sharing one checkout corrupt each other's
# git state. Extra invocations (cron overlap, manual) exit quietly.
exec 9>/tmp/improve-jarvis.lock
flock -n 9 || exit 0

LOG=~/jarvis-improve.log
exec >> "$LOG" 2>&1
echo "=== run started $(date -u) ==="

command -v claude >/dev/null || { echo "claude not installed"; exit 1; }
gh auth status >/dev/null 2>&1 || { echo "gh not logged in — run: gh auth login"; exit 1; }
cd "$(dirname "$0")/.." || exit 1

git checkout main -q && git pull -q

for i in $(seq 1 20); do
  echo "--- step attempt $i $(date -u) ---"
  claude -p "Read ROADMAP.md. Follow its per-step contract exactly: implement the
FIRST unchecked step only. If NO unchecked steps remain, instead follow the
'Autonomy loop instruction' at the bottom of PARITY.md: pick the top feasible ❌
feature, append a new properly-formatted phase to ROADMAP.md, commit that as its
own PR, and stop — the next run will implement it. Use .venv/bin/python -m pytest jarvis/tests -q to run
tests and never commit on red. Mark the step [x] and update JARVIS.md in the same
change. Then: git checkout -b feat/roadmap-step-N (N = the step number), commit,
push, and open a PR with gh pr create. Do NOT merge the PR. Finish by checking
out main. Do exactly one roadmap step, then stop." \
    --dangerously-skip-permissions \
    --max-turns 80 || { echo "claude exited nonzero (likely quota) — stopping"; break; }
  git checkout main -q && git pull -q
  sleep 30
done
echo "=== run finished $(date -u) ==="
