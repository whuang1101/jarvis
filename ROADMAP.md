# Jarvis Self-Improvement Roadmap — Path to Claude-Code-Level CLI

> **Who this is for:** Jarvis itself (or any model driving it) working through steps
> autonomously. Steps are ordered by dependency and sized so each one is a single
> focused change. **Do the steps in order. Do not skip verification.**
>
> **Rules for the executing model:**
> 1. Do ONE step at a time. Finish it (including verification) before starting the next.
> 2. After each step: reinstall (`python3 -m pipx reinstall jarvis`), confirm Jarvis starts,
>    mark the step `[x]` here, and update JARVIS.md if behavior changed.
> 3. Every 3–5 steps: branch, commit, PR, squash-merge (see JARVIS.md "Branching and PR workflow").
> 4. If a step fails twice, write what went wrong under the step and move to the next one.
> 5. Never edit `build/` or `.venv/`. Live source is `jarvis/`.

## Status & handoff

**Phases 0 and 1 are complete** (test suite + `/selftest`, tool-result truncation,
timeouts, auto-compact, 40-iteration cap with summary, `read_file` offset/limit,
Ctrl+C stream interrupt). **From Phase 2 onward, Jarvis executes this roadmap itself.**

To kick it off, the user starts Jarvis inside this repo and says:

```
/auto
Work through ROADMAP.md autonomously. Do one step at a time, in order.
```

Per-step loop (this is the contract — do not shortcut it):

1. Open ROADMAP.md, find the first `- [ ]` step. Re-read the files it names before editing.
2. Implement the step exactly as written. If it says "add a pytest", the step is not
   done until that test exists and passes.
3. Run the suite: `python3 -m pytest jarvis/tests -q` (or `/selftest`). Red → fix
   before anything else. Never reinstall on red.
4. Mark the step `[x]` here; update JARVIS.md (tool table / command list / key flows)
   in the same turn.
5. Write `~/.jarvis/resume.json` with
   `{"message": "Continue the next unchecked ROADMAP.md step.", "auto": true, "plan": false}`,
   then `python3 -m pipx reinstall jarvis` — it restarts you and resumes automatically.
6. Every 3–5 steps: branch → commit → push → `gh pr create` → `gh pr merge --squash
   --delete-branch` (details in JARVIS.md). Commit messages name the roadmap steps.

**When every step here is checked**, the roadmap refills itself: follow the
"Autonomy loop instruction" at the bottom of **PARITY.md** (the Claude Code
feature catalogue) — pick the next missing capability, append it here as a new
phase in this same step format, and keep going.

Steps marked *Verify: manual* need a human at the keyboard — implement them, note
"needs manual verification" under the step, and let the user confirm later rather
than blocking on it.

---

## Phase 0 — Safety net (do this FIRST; everything else depends on it)

The single biggest gap vs Claude Code: no tests. A self-improving CLI without tests
will eventually break itself and not notice.

- [x] **0.1 Test scaffolding.**
  Create `jarvis/tests/__init__.py` and `jarvis/tests/test_tools.py`. Add `pytest` to
  `[project.optional-dependencies] dev` in `pyproject.toml`. Write tests for the pure
  tools first (no network, no prompts): `edit_file` (unique-string rule: 0, 1, 2+
  occurrences), `read_file` (truncation at 10,000 chars), `list_dir`, `search_files`,
  `find_symbol`. Use `tmp_path` fixtures.
  *Verify:* `python3 -m pytest jarvis/tests/ -q` passes.

- [x] **0.2 Tests for context.py.**
  `jarvis/tests/test_context.py`: `_clean_history` (orphaned tool messages dropped),
  `_lookup_price` (longest-match: `gpt-4o-mini` ≠ `gpt-4o`), `token_estimate`.
  *Verify:* pytest passes.

- [x] **0.3 Tests for permissions.py.**
  `jarvis/tests/test_permissions.py`: `needs_permission` — every `_DESTRUCTIVE_RE`
  pattern matches; benign commands (`ls`, `git status`, `echo rm`) do not;
  `write_file`/`edit_file` always True.
  *Verify:* pytest passes.

- [x] **0.4 Self-check gate in the workflow.**
  Add a `/selftest` slash command in `commands.py` that runs
  `python3 -m pytest jarvis/tests/ -q` via subprocess and prints the result.
  Then update JARVIS.md's "Self-improvement workflow": step 6.5 = "run `/selftest`
  (or pytest directly) before reinstalling; if it fails, fix before proceeding."
  *Verify:* `/selftest` shows passing output. `_HELP_TEXT` updated.

---

## Phase 1 — Robustness (stop the agent from poisoning its own context)

These are all small, independent, and already listed in TODO.md § Robustness.

- [x] **1.1 Universal tool-result truncation.**
  In `agent.py`, after each `tool.execute()`, if the result exceeds 8,000 chars,
  keep the first 6,000 + last 1,500 and insert `\n[truncated — N chars omitted]\n`.
  Do it in ONE place (the agent loop), not per-tool.
  *Verify:* add a pytest for the truncation helper; run a command with huge output
  (`seq 1 100000`) and confirm the context doesn't blow up.

- [x] **1.2 `read_file` size guard.**
  In `read_file.py`: if file > 100KB, return an error string suggesting
  `search_files`/offset instead of dumping content. Add `offset`/`limit` line
  parameters (like Claude Code's Read) so big files are still usable.
  *Verify:* pytest with a generated 200KB file.

- [x] **1.3 Tool timeouts.**
  Wrap `tool.execute()` in the agent loop with a timeout (default 60s; use
  `concurrent.futures.ThreadPoolExecutor` + `future.result(timeout=...)`). On timeout
  return `"Error: tool timed out after 60s"` as the tool result — never crash the turn.
  *Verify:* pytest with a fake tool that sleeps.

- [x] **1.4 Auto-compact.**
  In `run_agent()` (agent.py), replace the 20K warning: when
  `context.token_estimate() > 25_000`, call `context.compact()` automatically and
  print a one-line notice. Keep the reactive compact-on-BadRequestError path.
  *Verify:* temporarily lower the threshold to 100, chat once, see it compact.
  Restore the threshold.

- [x] **1.5 Raise `_MAX_TOOL_ITERATIONS`.**
  10 is far too low for real agentic work (Claude Code does dozens). Raise to 40 in
  `agent.py`; when the cap is hit, instead of stopping silently, inject a user-role
  message "You hit the iteration limit — summarize progress and what remains" and do
  one final stream.
  *Verify:* code review + selftest; constant referenced nowhere else.

- [x] **1.6 Ctrl+C interrupts the stream, not the turn.**
  In `agent.py:_stream_turn`, catch `KeyboardInterrupt` during streaming: stop the
  Live render, keep the partial assistant text in history with a
  `[interrupted by user]` marker, and return to the prompt. In `cli.py`, ensure a
  second Ctrl+C at the empty prompt still exits.
  *Verify:* manual — start a long response, hit Ctrl+C, confirm you get a prompt back
  and `/history` shows the partial.

---

## Phase 2 — Configuration & permission rules (Claude Code's settings.json equivalent)

- [x] **2.1 `~/.jarvis/config.toml`.**
  New file `jarvis/settings.py`: load TOML (stdlib `tomllib`) from `~/.jarvis/config.toml`,
  with a frozen dataclass of defaults: `auto_mode: bool = false`,
  `max_tool_iterations: int = 40`, `autocompact_tokens: int = 25000`,
  `tool_timeout_secs: int = 60`, `theme: str = "monokai"`. Wire the constants from
  Phase 1 to read from it. Missing file = all defaults; malformed file = warn + defaults.
  *Verify:* pytest for the loader (missing, partial, malformed files).

- [x] **2.2 Per-project `.jarvis.toml` overrides.**
  In `settings.py`, after loading the global config, look for `.jarvis.toml` in cwd and
  up to 4 parents (same walk as `_find_jarvis_md`) and overlay its values.
  *Verify:* pytest.

- [x] **2.3 Permission allow/deny rules.**
  Add `[permissions] allow = []` / `deny = []` lists to the config (glob-style patterns
  like `run_command(git *)`, `write_file(*)`). In `permissions.py:needs_permission`,
  check deny first (deny → always prompt/refuse), then allow (allow → no prompt),
  then existing logic. This is the equivalent of Claude Code's permission rules.
  *Verify:* pytest covering allow, deny, and precedence.

- [x] **2.4 "Always allow" option in the prompt.**
  Extend `_arrow_confirm` in `permissions.py` from Yes/No to
  Yes / Yes-always-for-this-pattern / No. Choosing "always" appends the pattern to the
  in-memory allow list AND persists it to `~/.jarvis/config.toml`.
  *Verify:* manual — approve a `git push` with "always", confirm no prompt the second time
  and the pattern appears in config.toml.

- [x] **2.5 `/config` command.**
  `commands.py`: `/config` prints effective settings and their source (default /
  global / project); `/config <key> <value>` writes to the global TOML.
  *Verify:* manual + `_HELP_TEXT` updated.

---

## Phase 3 — Sessions (resume, list, one-shot mode)

- [x] **3.1 Non-interactive one-shot mode.**
  `cli.py`: support `jarvis -p "prompt"` (like `claude -p`) — run one agent turn with
  auto mode on, print the final answer, exit with code 0/1. Skip the banner and MCP
  connection unless `--mcp` is passed (startup speed matters for one-shots).
  *Verify:* `jarvis -p "what is 2+2"` prints an answer and exits.

- [x] **3.2 Session persistence.**
  New `jarvis/sessions.py`: on every turn, dump `context._history` as JSON to
  `~/.jarvis/sessions/<session-id>.json` (id = timestamp + short random suffix; store
  cwd and first user message as metadata). This is separate from the JSONL event log.
  *Verify:* pytest for save/load round-trip.

- [x] **3.3 `jarvis --continue` and `/resume`.**
  `--continue` loads the most recent session for the current cwd back into
  `ContextManager`. `/sessions` lists the last 10 (date, cwd, first message);
  `/resume <n>` loads one mid-REPL.
  *Verify:* manual — chat, exit, `jarvis --continue`, ask "what did we just discuss".

---

## Phase 4 — Extensibility (hooks, custom commands — the Claude Code power features)

- [x] **4.1 Custom slash commands from markdown.**
  In `commands.py`: if `cmd` doesn't match a built-in, look for
  `~/.jarvis/commands/<name>.md` then `.jarvis/commands/<name>.md` (project). File
  content is a prompt template; substitute `$ARGUMENTS` with the args; return
  `_RUN_AGENT_PREFIX + rendered`. `/help` lists discovered custom commands.
  *Verify:* create `~/.jarvis/commands/explain.md` containing
  "Explain this code simply: $ARGUMENTS", run `/explain context.py`.

- [x] **4.2 Pre/post tool hooks.**
  Config: `[hooks] pre_tool = [{match = "write_file", run = "..."}]`,
  `post_tool = [...]`. In the agent loop, before/after `execute()`, run matching hooks
  via subprocess with tool name + JSON args on stdin. Pre-hook exit code 2 blocks the
  tool (its stderr becomes the tool result). 10s timeout per hook.
  *Verify:* pytest with a hook script that blocks writes to a specific path.

- [x] **4.3 Streaming `run_command` output.**
  Use `subprocess.Popen` and print lines live through the console as the command runs
  (still return the captured, truncated text as the tool result). Keeps long test runs
  from looking frozen.
  *Verify:* manual — `sleep 1 && echo a && sleep 1 && echo b` prints incrementally.

- [x] **4.4 Background tasks.**
  `run_command` gains a `background: bool` param: launch detached, return a task id
  immediately, write output to `~/.jarvis/tasks/<id>.log`. Add a `task_output` tool to
  read a task's log/status. macOS notification via `osascript` on completion.
  *Verify:* run a 10s sleep in background, confirm REPL stays usable, read the output.

---

## Phase 5 — Agent quality (what actually makes Claude Code feel good)

- [x] **5.1 Todo/progress display.**
  New `todo_write` tool: model maintains a task list (content + status:
  pending/in_progress/completed); render it as a Rich checklist panel whenever it
  changes. Add a system-prompt nudge to use it for multi-step work. This doubles as
  the "plan display" TODO item.
  *Verify:* ask for a 3-step task; checklist renders and updates.

- [x] **5.2 System prompt tune-up.**
  Rewrite the base system prompt in `context.py` borrowing Claude Code's proven habits:
  be concise; prefer search before read, read before edit; verify after editing; never
  fabricate file contents; use the todo tool for multi-step work; ask before destructive
  actions. Keep it under ~600 words.
  *Verify:* selftest passes; a smoke conversation feels right.

- [x] **5.3 Better edit tool: `replace_all` + clearer errors.**
  `edit_file` gains optional `replace_all: bool`. On the 2+-occurrence error, include
  line numbers of each occurrence so the model can disambiguate without re-reading.
  Keep the permission preview in sync (permissions.py enforces the same rule).
  *Verify:* pytest for both behaviors.

- [x] **5.4 Subagent tool.**
  New `spawn_agent` tool: runs a fresh `run_agent` with its own `ContextManager`
  (same client/tracker), read-only tool set by default, up to 25 iterations, returns
  only the final text. Use it for "search the codebase for X" tasks so the main
  context stays small. Guard against recursion: a subagent cannot spawn subagents
  (pass a flag through).
  *Verify:* ask Jarvis to "use a subagent to find every place plan mode state is read".

- [ ] **5.5 `/review` and `/commit` workflow commands.**
  `/commit`: stage, generate a commit message from `git diff --staged`, commit (through
  the permission gate). `/review [pr#]`: fetch diff (`git diff main` or `gh pr diff`),
  run it through the agent with a review prompt. Both are `_RUN_AGENT_PREFIX` commands.
  *Verify:* manual on a scratch change.

---

## Phase 6 — Polish (nice-to-haves; pick from TODO.md as desired)

- [ ] 6.1 Multiline input (backslash continuation or triple-backtick blocks) — `cli.py`.
- [ ] 6.2 `/theme` for Rich syntax theme, persisted to config — `commands.py`.
- [ ] 6.3 `/diff` shows uncommitted changes — trivial `_RUN_AGENT_PREFIX` or direct git call.
- [ ] 6.4 `/pin` messages that survive `/compact` and `/clear` — `context.py`.
- [ ] 6.5 Image input support (paths → base64 vision content parts) — `context.py`, `cli.py`.
- [ ] 6.6 mypy in dev deps + fix errors; add to `/selftest`.
- [ ] 6.7 Structured logging levels + `--debug` flag.

---

## Standing orders (apply to every step)

- **Registration invariants:** new tool → `tools/__init__.py` `_REGISTRY` + JARVIS.md
  table. New command → `_HELP_TEXT` + JARVIS.md command list. New config key →
  documented in JARVIS.md.
- **All output through `formatter.py`;** tools return plain strings; errors are
  `"Error: ..."` strings, never exceptions.
- **Verification checklist after every edit** (from JARVIS.md): names defined/imported,
  imports exist, indentation right, new things wired up.
- **Definition of done for a step:** tests pass (`/selftest`), reinstall succeeds,
  Jarvis starts and answers a trivial prompt, this file and JARVIS.md updated.
