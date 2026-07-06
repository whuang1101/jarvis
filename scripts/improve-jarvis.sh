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

# Self-heal: a previous run may have left modified tracked files behind, which
# makes `git pull` abort. Reset tracked state to origin/main (leaves untracked
# files alone — never `git clean` here, the checkout may host unrelated dirs).
git fetch -q origin
git checkout main -q 2>/dev/null || git checkout -f main -q
git reset --hard -q origin/main
# Self-deploy: refresh deps in case main changed pyproject since the last run
.venv/bin/pip install -q -e ".[dev]" 2>/dev/null || true

# Model tiering: implementation steps are fully pre-specified, so Sonnet first
# (~5x more steps per quota batch); planning new roadmap phases is the hard
# thinking, so Opus first. Each falls back to the other if unavailable/erroring;
# only when the whole chain fails do we treat it as quota-exhausted and stop.
BUILD_MODELS="${JARVIS_LOOP_BUILD_MODELS:-sonnet opus}"
PLAN_MODELS="${JARVIS_LOOP_PLAN_MODELS:-opus sonnet}"

run_claude() {  # $1 = prompt, rest = model preference order
  local prompt="$1"; shift
  local m
  for m in "$@"; do
    if claude -p "$prompt" --model "$m" --dangerously-skip-permissions --max-turns 80; then
      return 0
    fi
    echo "model '$m' failed — trying next fallback"
  done
  return 1
}

for i in $(seq 1 20); do
  echo "--- step attempt $i $(date -u) ---"

  # Extract ONLY the next unchecked step so Claude never spends tokens reading
  # the whole roadmap. A step block runs from its '- [ ]' line to the next blank.
  STEP="$(awk '/^- \[ \] /{f=1} f && /^$/{exit} f{print}' ROADMAP.md)"

  if [ -n "$STEP" ]; then
    PROMPT="Repo conventions are in CLAUDE.md (already in your context — do not
re-read docs). Implement this single ROADMAP.md step, exactly as specified:

$STEP

Contract: code + tests + the 1-3 line JARVIS.md update in one commit on branch
feat/roadmap-step-N (N = step number). Mark the step [x] in ROADMAP.md in the
same commit. Run .venv/bin/python -m pytest jarvis/tests -q; never commit on
red. Then: push, gh pr create, gh pr checks --watch, and merge ONLY if CI is
green: gh pr merge --squash --delete-branch (if CI fails, fix on the branch and
push again). If the merge is blocked by conflicts, run git fetch origin && git
merge origin/main, resolve the conflicts preserving BOTH sides' features,
re-run the tests, push, and merge once checks pass — do not leave the PR open.
Finish with git checkout main && git pull. Do nothing beyond this one step."
  else
    PROMPT="ROADMAP.md has no unchecked steps. Follow the 'Autonomy loop
instruction' at the bottom of PARITY.md: pick the top feasible ❌ feature,
append it to ROADMAP.md as a new properly-formatted phase (2-6 steps, files +
*Verify:* line each), and ship that roadmap edit as its own PR (create, watch
checks, squash-merge, back to main). Do not implement the feature yet."
  fi

  if [ -n "$STEP" ]; then
    run_claude "$PROMPT" $BUILD_MODELS || { echo "all models failed (likely quota) — stopping"; break; }
  else
    run_claude "$PROMPT" $PLAN_MODELS || { echo "all models failed (likely quota) — stopping"; break; }
  fi
  git checkout main -q && git pull -q
  sleep 30
done
echo "=== run finished $(date -u) ==="
