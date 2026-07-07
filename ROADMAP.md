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

- [x] **5.5 `/review` and `/commit` workflow commands.**
  `/commit`: stage, generate a commit message from `git diff --staged`, commit (through
  the permission gate). `/review [pr#]`: fetch diff (`git diff main` or `gh pr diff`),
  run it through the agent with a review prompt. Both are `_RUN_AGENT_PREFIX` commands.
  *Verify:* manual on a scratch change.

---

## Phase 6 — Polish (nice-to-haves; pick from TODO.md as desired)

- [x] 6.1 Multiline input (backslash continuation or triple-backtick blocks) — `cli.py`.
- [x] 6.2 `/theme` for Rich syntax theme, persisted to config — `commands.py`.
- [x] 6.3 `/diff` shows uncommitted changes — trivial `_RUN_AGENT_PREFIX` or direct git call.
- [x] 6.4 `/pin` messages that survive `/compact` and `/clear` — `context.py`.
- [x] 6.5 Image input support (paths → base64 vision content parts) — `context.py`, `cli.py`.
- [x] 6.6 mypy in dev deps + fix errors; add to `/selftest`.
- [x] 6.7 Structured logging levels + `--debug` flag.

---

## Phase 7 — Extended thinking / reasoning display

PARITY.md "Extended thinking / reasoning display" (Core agent loop). Reasoning
models surface their chain-of-thought as a separate stream field; render it
distinctly (dimmed, above the answer) instead of dropping it. Graceful when the
deployment emits no reasoning — nothing changes for non-reasoning models.

- [x] **7.1 Request + config toggle.**
  Add a `show_thinking: bool = True` field to the `Settings` dataclass in
  `settings.py` (documented in JARVIS.md config section). In `client.py:stream()`,
  keep the request unchanged for now — reasoning content arrives on the delta
  regardless — but read the toggle so 7.2 can honor it.
  *Verify:* pytest asserts `Settings()` defaults `show_thinking` True and that a
  `.jarvis.toml` overlay can set it False.

- [x] **7.2 Render reasoning deltas distinctly.**
  In `agent.py:_stream_turn`'s `drain()`, accumulate `getattr(delta, "reasoning_content", None)`
  (Azure) / `delta.reasoning` into a separate `state["thinking"]` buffer, gated on
  `settings.show_thinking`. Add a `formatter.py` helper `print_thinking_header()` +
  render the reasoning as dimmed italic markdown in its own live block that closes
  before the answer's `⏺` header prints. Never mix reasoning into `state["text"]`
  (it must not be sent back as assistant content).
  *Verify:* pytest drives `_stream_turn` with a fake stream whose chunks carry
  `reasoning_content` then `content`; assert returned `full_text` excludes the
  reasoning and the thinking buffer captured it.

- [x] **7.3 Docs + parity flip.**
  Update JARVIS.md (settings table + a one-line note on reasoning rendering) and
  flip PARITY.md's "Extended thinking / reasoning display" row from ❌ to ✅.
  *Verify:* `/selftest` (pytest) green; grep confirms the PARITY row is ✅.

---

## Phase 8 — Read PDFs / Jupyter notebooks

PARITY.md "Read PDFs / Jupyter notebooks" (Tools). `read_file` currently only
handles UTF-8 text; pointing it at a `.ipynb` yields raw JSON noise and a `.pdf`
yields replaced binary bytes. Teach `read_file` to detect these two formats and
return clean, model-readable text. Notebooks need no new dependency (they are
JSON); PDFs add `pypdf`. In both cases the extraction happens BEFORE the
`_MAX_FULL_READ_BYTES` guard (the raw file is binary/large but the extracted text
is small), and the existing `_TRUNCATE_AT` cap still applies to the result.

- [x] **8.1 Jupyter notebook rendering.**
  Add `jarvis/tools/documents.py` with `render_notebook(path: str) -> str`: parse
  the `.ipynb` JSON and emit each cell as a labeled block — `# %% [markdown]` /
  `# %% [code]` headers, the joined `source`, and for code cells a compact
  `# Out:` section from `outputs` (stream `text`, `text/plain` data; skip images).
  Return `"Error: ..."` strings on bad JSON / missing keys, never raise. In
  `read_file.py`, dispatch to `render_notebook` when the path ends in `.ipynb`
  (case-insensitive), before the size guard; apply `_TRUNCATE_AT` to the result.
  *Verify:* pytest builds a tiny in-memory notebook dict, writes it to a tmp
  `.ipynb`, and asserts `ReadFileTool().execute` returns markdown source, code
  source, and the `# Out:` text while excluding the raw `"cell_type"` JSON keys;
  a malformed `.ipynb` returns an `"Error:"` string.

- [x] **8.2 PDF text extraction.**
  Add `pypdf>=4.0` to `dependencies` in `pyproject.toml`. In `documents.py` add
  `extract_pdf_text(path: str) -> str`: open with `pypdf.PdfReader`, concatenate
  `page.extract_text()` across pages with `\n\n--- page N ---\n\n` separators,
  and return `"Error: ..."` on `pypdf`/OSError (import `pypdf` lazily inside the
  function so a missing wheel degrades to an error string, not an import crash).
  Dispatch in `read_file.py` for paths ending in `.pdf` (case-insensitive),
  before the size guard, with `_TRUNCATE_AT` applied.
  *Verify:* pytest generates a minimal one-page PDF (write a fixed byte string,
  or build one with `pypdf` if available) and asserts the extracted text appears
  in `ReadFileTool().execute`'s output; a non-PDF file passed with a `.pdf` name
  returns an `"Error:"` string rather than raising.

- [x] **8.3 Docs + parity flip.**
  Update JARVIS.md's `read_file` tool-table row to note `.ipynb`/`.pdf` are
  auto-detected and rendered as text, and add `pypdf` to any dependency list in
  JARVIS.md. Flip PARITY.md's "Read PDFs / Jupyter notebooks" row from ❌ to ✅.
  *Verify:* `/selftest` (pytest) green; grep confirms the PARITY row is ✅ and
  JARVIS.md mentions `.ipynb`.

---

## Phase 9 — Glob tool (fast file lookup by pattern)

*The top PARITY sections have several stale ❌ rows for features that already
shipped (todo list = `todo_write`, subagents = `spawn_agent`, bash background =
`run_command background`/`task_output`, image/vision paths = `build_multimodal_content`).
The topmost genuinely-missing, self-contained tool is `Glob (find files by
pattern)` — a name/path lookup that's cheaper than `list_dir` + `search_files`
when you already know the filename shape.*

- [x] **9.1 Glob tool.**
  Add `jarvis/tools/glob_files.py` with `GlobFilesTool(BaseTool)`, `name = "glob"`.
  Parameters: `pattern` (required, a glob like `**/*.py` or `src/*.ts`) and optional
  `path` (root directory to search from, default `"."`). In `execute`, resolve the
  root via `Path(path).expanduser()`, return `"Error: path not found: ..."` if it
  doesn't exist / isn't a directory, then collect matches with `root.glob(pattern)`.
  Keep only files, skip any match whose path parts start with `.` (hidden/`.git`),
  sort by `st_mtime` descending (newest first), cap at 200 entries (append a
  `"[... N more]"` note when truncated), and return the relative paths joined by
  newlines — or `"No files match <pattern>"` when empty. Never raise: wrap the glob
  call and catch bad patterns / `OSError` as `"Error: ..."` strings. Register the
  tool in `jarvis/tools/__init__.py` (`import` + add `GlobFilesTool()` to `_REGISTRY`).
  *Verify:* pytest builds a tmp tree (e.g. `a.py`, `sub/b.py`, `sub/.hidden.py`),
  asserts `glob` with `**/*.py` returns `a.py` and `sub/b.py` (not the hidden one)
  newest-first, returns the `"No files match"` string for a non-matching pattern,
  and returns an `"Error: ..."` string for a missing root path.

- [x] **9.2 Docs + parity flip.**
  Add a `glob_files.py` row to the tool tree in JARVIS.md (one line: "Find files by
  glob pattern, newest-first, capped at 200"). Flip PARITY.md's
  `Glob (find files by pattern)` row from ❌ to ✅.
  *Verify:* `/selftest` (pytest) green; grep confirms the PARITY Glob row is ✅ and
  JARVIS.md mentions `glob_files.py`.

---

## Phase 10 — Sensitive-file protection (secrets excluded from reads & searches)

*Most of the upstream PARITY ❌ rows above this one are already stale: allow/deny
pattern rules and the persistent "Always" option live in `permissions.py`
(`permission_allow`/`permission_deny` + `_add_allow_pattern`), background and
live-streamed command output live in `run_command.py`, and the todo/subagent/
glob/vision rows all shipped. The topmost genuinely-missing, self-contained item
is `Sensitive-file protection (.env etc. excluded from reads)` — nothing in
`read_file.py`, `search_files.py`, or `list_dir.py` guards secret files, so a
stray `read_file .env` or `search_files SECRET` leaks credentials straight into
the transcript.*

- [x] **10.1 Sensitive-path helper.**
  Add `jarvis/tools/sensitive.py` with a module-level tuple
  `_SENSITIVE_GLOBS = (".env", ".env.*", "*.pem", "*.key", "id_rsa", "id_dsa",
  "id_ecdsa", "id_ed25519", "*.p12", "*.pfx", "credentials", ".netrc",
  ".pgpass", "*.keystore")` (all lowercase) and two functions. `is_sensitive_path(path: str) -> bool`:
  take `os.path.basename(path.rstrip("/"))`, lowercase it, and return `True` when
  `fnmatch.fnmatch(name, glob)` matches any entry; wrap in try/except and return
  `False` on any error, never raise. `sensitive_read_error(path: str) -> str`:
  return `f"Error: refusing to read sensitive file {path} — it matches a secret-file
  pattern. Enable dangerously_skip_permissions to override."`.
  *Verify:* pytest asserts `is_sensitive_path` is `True` for `.env`,
  `/tmp/proj/.env.local`, `key.pem`, `id_rsa`, and `~/.netrc`, and `False` for
  `main.py`, `README.env.md`, and `envvars.py`; `sensitive_read_error("x")` returns
  a string starting with `"Error:"`.

- [x] **10.2 Wire the guard into read_file and search_files.**
  In `read_file.py:execute`, before the `os.path.getsize` call, lazily import
  `from .sensitive import is_sensitive_path, sensitive_read_error` and
  `from ..permissions import is_dangerously_skip_permissions` (inside the method,
  to avoid an import cycle), then
  `if is_sensitive_path(path) and not is_dangerously_skip_permissions(): return sensitive_read_error(path)`.
  In `search_files.py:execute`, import `_SENSITIVE_GLOBS` and `is_sensitive_path`
  from `.sensitive`; unless `is_dangerously_skip_permissions()` is set, append a
  `--exclude=<glob>` argument to the `grep` invocation for each entry in
  `_SENSITIVE_GLOBS` and post-filter the result lines, dropping any whose file
  path (the text before the first `:`) is sensitive per `is_sensitive_path`.
  *Verify:* pytest writes a tmp `.env` containing `SECRET=abc123`;
  `ReadFileTool().execute({"path": env_path})` returns a string containing
  `"refusing to read sensitive file"` and NOT `abc123`, while a sibling `notes.txt`
  still reads normally; `SearchFilesTool().execute({"pattern": "SECRET", "directory": tmp})`
  (with `SECRET` present in both `.env` and `notes.txt`) returns the `notes.txt`
  match but neither the `.env` path nor `abc123`.

- [x] **10.3 Docs + parity flip.**
  Update JARVIS.md's `read_file` and `search_files` rows to note that secret-file
  patterns (`.env`, `*.pem`, `id_rsa`, …) are blocked from reads/searches unless
  `dangerously_skip_permissions` is enabled, and mention `sensitive.py` in the tool
  tree. Flip PARITY.md's `Sensitive-file protection (.env etc. excluded from reads)`
  row from ❌ to ✅.
  *Verify:* `/selftest` (pytest) green; grep confirms the PARITY sensitive-file row
  is ✅ and JARVIS.md mentions `sensitive.py`.

---

## Phase 11 — Quick-memory `#` shortcut (append a memory from the prompt)

*The remaining PARITY ❌ rows above the sensitive-file item that just shipped are
either already-implemented-but-stale (todo/subagent/vision, background & streamed
command output, allow/deny + persistent "Always" rules, the settings overlay, and
`--continue`/session-listing all live in the tree) or earmarked big phases that
need OS-level tooling and policy decisions (`Sandboxed command execution` is a
whole Phase-6-scale security item, not a self-contained increment). The topmost
genuinely-missing, self-contained, human-resource-free item is the `#` shortcut to
append a memory quickly: `/memory add …` and `~/.jarvis/memory.md` already exist,
but there is no one-keystroke `#text` path at the prompt, so quick notes force the
user through the full slash command.*

- [x] **11.1 `append_memory` helper.**
  In `jarvis/commands.py`, add a module-level function `append_memory(text: str) -> str`
  that resolves `Path("~/.jarvis/memory.md").expanduser()`, `mkdir(parents=True,
  exist_ok=True)` on its parent, appends `text.strip() + "\n"` to it, and returns
  `"Memory updated."` on success or `f"Error: failed to add to memory: {e}"` on any
  exception (wrap in try/except, never raise). Refactor the existing `/memory add `
  branch (around `commands.py:274`) to call `append_memory(text_to_add)` and print
  its return string via the existing formatter helper instead of duplicating the
  open/write logic.
  *Verify:* pytest monkeypatches `Path.home` to `tmp_path`, asserts
  `append_memory("recall this")` returns `"Memory updated."` and that
  `tmp_path/".jarvis/memory.md"` then contains `"recall this"`; a second call
  appends a second line (file has both). Existing `/memory` tests stay green.

- [x] **11.2 Wire the `#` shortcut into the input loop.**
  In `jarvis/cli.py`, in the main REPL loop after the empty-input guard (around
  `cli.py:324`) and **before** the `if user_input.startswith("/")` dispatch, add a
  branch: `if user_input.startswith("#"):` extract `note = user_input[1:].strip()`,
  and if `note` is non-empty lazily `from .commands import append_memory` and print
  its result through the existing `print_system`/formatter helper; then `continue`
  the loop so the text is never sent to the agent (a bare `#` with no text is
  swallowed with no error). Add a `#text` line to the `/memory` entry in
  `commands.py:_HELP_TEXT` documenting the shortcut.
  *Verify:* pytest reuses the 11.1 `append_memory` coverage; grep confirms
  `cli.py` contains `user_input.startswith("#")` calling `append_memory` and that
  `_HELP_TEXT` mentions the `#` shortcut. `/selftest` (pytest) green.

- [x] **11.3 Docs + parity flip.**
  In JARVIS.md, note under the memory/commands section that a leading `#` at the
  prompt appends the rest of the line to `~/.jarvis/memory.md` (equivalent to
  `/memory add`). Flip PARITY.md's `# shortcut to append a memory quickly` row from
  ❌ to ✅.
  *Verify:* `/selftest` (pytest) green; grep confirms the PARITY `#` shortcut row is
  ✅ and JARVIS.md mentions the `#` memory shortcut.

---

## Phase 12 — `@path` file mentions (inline a file into the prompt)

*Re-surveying PARITY top-to-bottom, the ❌ rows above this one are either
already-shipped-but-stale (todo list, subagents, vision image input, background &
streamed command output, allow/deny + persistent "Always" rules, the settings
overlay, and `--continue`/`/sessions`/`/resume` all live in the tree) or large
non-self-contained phases the loop is allowed to skip: `Sandboxed command
execution` needs OS-level tooling (bubblewrap / sandbox-exec) that the pytest CI
can't exercise, and `/rewind` is an explicitly "big" multi-phase checkpoint-and-
restore effort, not a single increment. The topmost genuinely-missing, self-
contained, human-resource-free item is `@file` mentions: a `/file` command already
loads a whole file into context, but there is no inline `@path` in an ordinary
message, so referencing a file mid-sentence forces the user to break flow and run a
command first. The scan mirrors the existing `build_multimodal_content` image
helper, so it drops in beside it.*

- [x] **12.1 `expand_file_mentions` helper.**
  In `jarvis/context.py`, next to `build_multimodal_content` (around
  `context.py:20`), add `expand_file_mentions(text: str) -> str`. Split `text` on
  whitespace; for every token starting with `@`, strip the leading `@` and any
  trailing sentence punctuation (`text.rstrip("?.,!:;)")` on the remainder), and
  keep the candidate if `Path(candidate).is_file()` **and** its suffix is NOT in the
  existing `_IMAGE_EXTENSIONS` set (image `@mentions` are left untouched so
  `build_multimodal_content` still routes them to vision). For each surviving path,
  read it with `open(..., encoding="utf-8", errors="replace")` inside a
  `try/except OSError` (on failure skip that mention silently, never raise) and
  collect its content. If no mentions resolve, return `text` unchanged; otherwise
  return `text` with, appended once per file, a block matching the `/file` command's
  format (`commands.py:544`): `f"\n\n[File: {path}]\n\`\`\`\n{content}\n\`\`\`"`. The
  original `@path` token stays in the message so the model sees the reference.
  *Verify:* pytest writes a `notes.txt` containing `"hello world"` under `tmp_path`
  and asserts `expand_file_mentions(f"summarize @{notes} please")` returns a string
  containing both `"[File:"` and `"hello world"`; a `@missing.txt` token that has no
  file returns the text unchanged; a `@shot.png` token pointing at a real image file
  is returned unchanged (left for the vision path). Existing `test_context.py` tests
  stay green.

- [x] **12.2 Wire `@path` expansion into the input loop.**
  In `jarvis/cli.py`, extend the existing import at `cli.py:56` to also import
  `expand_file_mentions` from `.context`, and at the agent dispatch (`cli.py:354`)
  wrap the input so mentions expand before the multimodal/image scan:
  `run_agent(build_multimodal_content(expand_file_mentions(user_input)), client,
  context, tracker, logger, session)`. Add a line to the `/file` entry in
  `commands.py:_HELP_TEXT` documenting that an inline `@path` in any message pulls
  that file's contents in without the command (images still route to vision).
  *Verify:* grep confirms `cli.py` imports `expand_file_mentions` and that
  `cli.py:354` nests `expand_file_mentions(user_input)` inside
  `build_multimodal_content(...)`, and that `_HELP_TEXT` mentions `@path`.
  `/selftest` (pytest) green.

- [x] **12.3 Docs + parity flip.**
  In JARVIS.md, note under the commands/input section that typing an inline `@path`
  in a normal message attaches that file's contents (equivalent to `/file`, but
  usable mid-sentence and stackable with the surrounding text); image `@mentions`
  continue to route to vision. Flip PARITY.md's `@file mentions to pull files into a
  message` row from ❌ to ✅.
  *Verify:* `/selftest` (pytest) green; grep confirms the PARITY `@file mentions`
  row is ✅ and JARVIS.md mentions the inline `@path` file syntax.

---

## Phase 13 — Pipe stdin as the prompt in headless mode

*Re-surveying PARITY top-to-bottom, the ❌ rows above this one are again either
already-shipped-but-stale (todo list, subagents, vision input, background & streamed
command output, allow/deny + persistent "Always" rules, the settings overlay,
`--continue`/`/sessions`/`/resume`, `/commit`, `/review`, and the `@file` mentions
Phase 12 just landed) or items the loop is allowed to skip. `Prompt caching / cost
optimization` is flagged N/A on Azure and has nothing a pytest run can exercise;
`--output-format json / stream-json` cannot go in cleanly because machine-readable
stdout requires threading a quiet/no-render flag through the Rich `Live` streaming
loop in `agent.py`, so it is not a single self-contained increment; `--model` is
entangled with the Azure-deployment `Config`. That leaves the topmost genuinely-
missing, self-contained, human-resource-free headless item: piping stdin as the
prompt (`cat err.log | jarvis -p "fix"`). `-p` one-shot already exists but ignores a
piped stdin, so the common `command | jarvis` shell idiom drops its input on the
floor. The change is confined to `cli.py` argument dispatch and is unit-testable by
monkeypatching `sys.stdin`, with no Azure call needed.*

- [x] **13.1 `_read_piped_stdin` helper.**
  In `jarvis/cli.py`, add `_read_piped_stdin() -> str | None`. Guard on
  `sys.stdin.isatty()` FIRST and return `None` when it is a TTY (interactive REPL —
  never read, or it would block). Otherwise `sys.stdin.read()`, and return the text
  with trailing newlines stripped, or `None` if it is empty/whitespace-only. Wrap the
  read in `try/except (OSError, ValueError)` returning `None` on failure so a closed
  or unreadable stdin never crashes startup.
  *Verify:* add cases to `jarvis/tests/test_cli.py` that monkeypatch `sys.stdin` with
  a fake object: `isatty()` → `True` yields `None` (and `.read` is never called);
  `isatty()` → `False` with `"boom\n"` yields `"boom"`; `"   "` yields `None`.
  `/selftest` (pytest) green.

- [x] **13.2 Compose the effective one-shot prompt.**
  In `jarvis/cli.py`, add a pure helper
  `_compose_one_shot_prompt(prompt: str | None, piped: str | None) -> str | None`:
  return `None` when both are absent; return `prompt` alone when nothing is piped;
  return `piped` alone when there is no `-p`; and when both exist join them as
  `f"{prompt}\n\n{piped}"` so the model sees the instruction followed by the piped
  payload. In `main()` (`cli.py:217`), compute `piped = _read_piped_stdin()` and
  `effective = _compose_one_shot_prompt(args.prompt, piped)`; when `effective is not
  None`, call `_run_one_shot(effective, connect_mcp=args.mcp, debug=args.debug)`
  instead of gating one-shot solely on `args.prompt is not None`, so a bare
  `cat x | jarvis` also runs headless.
  *Verify:* `jarvis/tests/test_cli.py` asserts all four `_compose_one_shot_prompt`
  branches (None/None → None; prompt-only → prompt; piped-only → piped; both →
  `"p\n\nq"`). `/selftest` (pytest) green.

- [x] **13.3 Docs + parity flip.**
  In JARVIS.md, note under the headless / CLI section that Jarvis reads piped stdin
  in one-shot mode: `cat err.log | jarvis -p "fix this"` appends the piped text below
  the `-p` prompt, and a bare `command | jarvis` uses the piped text as the whole
  prompt (an interactive TTY is never read). Flip PARITY.md's `Pipe stdin as prompt`
  row from ❌ to ✅.
  *Verify:* `/selftest` (pytest) green; grep confirms the PARITY `Pipe stdin as
  prompt` row is ✅ and JARVIS.md documents `| jarvis`.

---

## Phase 14 — `--max-turns` and `--model` headless flags

*Re-surveying PARITY top-to-bottom, the ❌ rows above this one are again either
already-shipped-but-stale (todo list, subagents, vision input, background &
streamed command output, allow/deny + persistent "Always" rules, the settings
overlay, `--continue`/`/sessions`/`/resume`, `/commit`, `/review`, `@file`
mentions, and the piped-stdin one-shot Phase 13 just landed) or items the loop is
allowed to skip: `Prompt caching / cost optimization` is flagged N/A on Azure and
has nothing a pytest run can exercise; `Sandboxed command execution` is a whole
Phase-6-scale OS-level security item (bubblewrap / sandbox-exec) the CI cannot
drive; `/rewind` is explicitly "big"; and `--output-format json / stream-json`
needs a quiet/no-render flag threaded through the Rich `Live` streaming loop in
`agent.py`, so it is not a single self-contained increment. That leaves the
topmost genuinely-missing, self-contained, human-resource-free headless item:
`--max-turns, --model flags`. One-shot mode already exists but the tool-iteration
cap is fixed at `Settings.max_tool_iterations` and the Azure deployment is fixed
by `Config.load()`, so a caller cannot bound a headless run or point it at a
different deployment. `run_agent` already accepts `max_iterations`, and `Config`
is a frozen dataclass overridable via `dataclasses.replace`, so both flags are
confined to `cli.py` argument dispatch and unit-testable through `_parse_args`
(and a `Config.load` override) with no Azure call needed.

- [x] **14.1 `--max-turns` flag wired into the one-shot cap.**
  In `jarvis/cli.py`, add a `parser.add_argument("--max-turns", dest="max_turns",
  type=int, default=None, metavar="N", help=...)` to `_parse_args` (help: "Cap the
  tool-call iterations for a one-shot run; default uses the configured
  max_tool_iterations."). Thread it through: give `_run_one_shot` a new
  `max_turns: int | None = None` parameter, pass it as
  `run_agent(prompt, client, context, tracker, logger, session, max_iterations=max_turns)`
  (keyword form; `run_agent` already accepts `max_iterations`), and in `main()`
  update the `_run_one_shot(...)` call to pass `max_turns=args.max_turns`.
  *Verify:* add `test_cli.py` cases asserting `_parse_args([]).max_turns is None`
  and `_parse_args(["--max-turns", "3"]).max_turns == 3`. `/selftest` (pytest) green.

- [x] **14.2 `--model` flag overrides the Azure deployment.**
  In `jarvis/cli.py`, add `parser.add_argument("--model", dest="model",
  default=None, metavar="DEPLOYMENT", help="Override the Azure deployment name for
  this run.")`. In `_run_one_shot`, add a `model: str | None = None` parameter and,
  after `config = Config.load()`, do `if model: config = dataclasses.replace(config,
  deployment=model)` (add `import dataclasses` at the top of `cli.py`) before
  constructing `JarvisClient(config)`. In `main()`, pass `model=args.model` to
  `_run_one_shot(...)`, and also apply the same `dataclasses.replace` override to the
  interactive `config` right after its `Config.load()` so `jarvis --model X` works in
  the REPL too.
  *Verify:* add a `test_cli.py` case asserting `_parse_args(["--model", "gpt-4o"]).model
  == "gpt-4o"` and `_parse_args([]).model is None`; add a test that
  `dataclasses.replace(Config(endpoint="e", api_key="k", deployment="d",
  api_version="v"), deployment="gpt-4o").deployment == "gpt-4o"` (constructs a Config
  directly, no `.load()` / no env). `/selftest` (pytest) green.

- [x] **14.3 Docs + parity flip.**
  In JARVIS.md, note under the headless / CLI section that `--max-turns N` caps a
  one-shot run's tool iterations and `--model DEPLOYMENT` overrides the Azure
  deployment for the run (both interactive and `-p`). Flip PARITY.md's
  `--max-turns, --model flags` row from ❌ to ✅.
  *Verify:* `/selftest` (pytest) green; grep confirms the PARITY `--max-turns` row is
  ✅ and JARVIS.md documents `--max-turns` and `--model`.

---

## Phase 15 — `--output-format json` / `stream-json` for headless mode

*Re-surveying PARITY top-to-bottom, the ❌ rows above this one are once more all
already-shipped-but-stale — todo list, subagents, vision input, background &
streamed command output, allow/deny + persistent "Always" rules, the settings
overlay, `--continue`/`/sessions`/`/resume` (session picker with metadata),
custom markdown commands, and PreToolUse/PostToolUse hooks are every one of them
present in the tree — or items the loop skips: `Prompt caching / cost
optimization` is flagged N/A on Azure with nothing a pytest run can exercise;
`Sandboxed command execution` is a Phase-6-scale OS-level security item CI cannot
drive; and `/rewind` is explicitly "big" (shadow-git file checkpoints on a live
repo, unsafe to build unattended). That leaves the topmost genuinely-missing,
human-resource-free headless item: `--output-format json / stream-json`. Phase 14
deferred it as "not a single self-contained increment" — which is exactly what a
multi-step phase is for. One-shot mode (`-p`) already exists and `run_agent`
already returns the final assistant text, but everything renders through the Rich
`console` in `formatter.py` (which `agent.py` imports directly), so stdout is
human-formatted markdown, not machine-readable. The fix is confined to `cli.py`
and `formatter.py`: divert the Rich `console` to stderr for non-text formats
(Rich `Console` exposes a `file` setter, so one assignment reroutes every
`console.print`/`console.status`/`Live` call without touching `agent.py`'s
imported binding), then emit a JSON result object (or newline-delimited event
objects) on stdout. Every step is unit-testable through `_parse_args`, a pure
payload builder, and an emitter writing to an in-memory stream — no Azure call.

- [x] **15.1 Add `--output-format` and route human render to stderr.**
  In `jarvis/cli.py` `_parse_args`, add
  `parser.add_argument("--output-format", dest="output_format",
  choices=("text", "json", "stream-json"), default="text", help="Headless output
  format for -p mode: text (default human render), json (one result object), or
  stream-json (newline-delimited event objects).")`. In `jarvis/formatter.py`, add
  `def redirect_console(file) -> None:` that sets the module `console.file = file`
  (Rich `Console`'s `file` setter), so every existing `console.print` /
  `console.status` / `Live` render call is diverted at once — no change to
  `agent.py`, which imports `console` by binding.
  *Verify:* add `test_cli.py` cases asserting `_parse_args([]).output_format ==
  "text"`, `_parse_args(["--output-format", "json"]).output_format == "json"`, and
  that `_parse_args(["--output-format", "bogus"])` raises `SystemExit`; add a case
  that after `import sys; jarvis.formatter.redirect_console(sys.stderr)` then
  `jarvis.formatter.console.file is sys.stderr` (reset to `sys.stdout` after).
  `/selftest` (pytest) green.

- [x] **15.2 Pure result-payload builder and stdout emitter.**
  In `jarvis/cli.py`, add `def _result_payload(result: str, is_error: bool,
  tracker: UsageTracker) -> dict` returning
  `{"type": "result", "subtype": "error" if is_error else "success", "is_error":
  is_error, "result": result, "usage": {"input_tokens": tracker.prompt_tokens,
  "output_tokens": tracker.completion_tokens}}` (mirrors Claude Code's headless
  result shape closely enough to be scriptable). Add `def _emit_result(fmt: str,
  payload: dict, init_meta: dict, out) -> None` that, for `fmt == "json"`, writes
  `json.dumps(payload)` + newline to `out`; for `fmt == "stream-json"`, writes two
  lines — `json.dumps({"type": "system", "subtype": "init", **init_meta})` then
  `json.dumps(payload)`, each newline-terminated; for `fmt == "text"`, writes
  nothing (text mode already rendered live). Both helpers are pure (no Azure, no
  `sys.exit`).
  *Verify:* add `test_cli.py` cases: `_result_payload("hi", False, tracker)` (with a
  `UsageTracker` whose `prompt_tokens`/`completion_tokens` were set via `.record(...)`)
  has `subtype == "success"`, `is_error is False`, `result == "hi"`, and the `usage`
  numbers; and that `_emit_result("stream-json", payload, {"model": "d"}, buf)` with
  `buf = io.StringIO()` writes exactly two lines that each `json.loads` cleanly, the
  first `type == "system"` and the second `type == "result"`. `/selftest` (pytest) green.

- [x] **15.3 Wire the formats into `_run_one_shot` and `main()`.**
  In `jarvis/cli.py`, give `_run_one_shot` an `output_format: str = "text"`
  parameter. When `output_format != "text"`, call
  `formatter.redirect_console(sys.stderr)` before running so all render goes to
  stderr and stdout stays clean. Capture `result = run_agent(...)` (it already
  returns the final text); on the `except` branch set `result = str(e)`,
  `is_error = True`, `exit_code = 1` (keep the existing `print_error`, now on
  stderr). After the run, call `_emit_result(output_format,
  _result_payload(result, is_error, tracker), {"model": client.current_deployment(),
  "cwd": os.getcwd()}, sys.stdout)` before `sys.exit(exit_code)`. In `main()`, pass
  `output_format=args.output_format` into the `_run_one_shot(...)` call.
  *Verify:* add a `test_cli.py` case that monkeypatches `cli.run_agent` to return
  `"canned answer"`, `cli.Config` and `cli.JarvisClient` to the existing
  `_FakeConfig`/`_FakeClient`, and `cli.SessionLogger`, then calls
  `_run_one_shot("q", connect_mcp=False, output_format="json")` inside
  `pytest.raises(SystemExit)` with `capsys`; assert the captured stdout parses as
  JSON with `type == "result"` and `result == "canned answer"`. `/selftest` (pytest) green.

- [x] **15.4 Docs + parity flip.**
  In JARVIS.md, note under the headless / CLI section that `--output-format json`
  prints a single `{"type":"result",...}` object and `--output-format stream-json`
  prints newline-delimited event objects (init + result), with human render sent to
  stderr so stdout stays machine-readable. Flip PARITY.md's
  `--output-format json / stream-json` row from ❌ to ✅ (note in the row that
  per-tool event lines are a follow-up if 15.3 emits only init + result).
  *Verify:* `/selftest` (pytest) green; grep confirms the PARITY `--output-format`
  row is no longer ❌ and JARVIS.md documents `--output-format`.

---

## Phase 16 — Maintained todo list (persistent state + recall + agent awareness)

PARITY row "Todo list the agent maintains (TaskCreate-style) with live checklist
UI" is ❌: `todo_write` today only *prints* a one-shot panel (`formatter.print_todo_list`)
and keeps nothing — there is no maintained state, no way to recall the current list,
and the agent forgets its own plan between turns. This phase adds a session-scoped
store, a `/todos` command, and a system-prompt reminder so the agent actually
"maintains" the checklist. No new Azure calls; mirrors the existing `tasks.py`
module-level-store pattern.

- [x] **16.1 In-memory todo store the tool writes into.**
  Add `jarvis/todos.py` with a module-level `_TODOS: list[dict[str, str]] = []` and:
  `set_todos(todos: list[dict[str, str]]) -> None` (replaces the list, storing a
  deep-ish copy — `[dict(t) for t in todos]` — so callers can't mutate internal
  state), `get_todos() -> list[dict[str, str]]` (returns a fresh copy list of
  copies, never the internal object), `clear_todos() -> None` (empties it), and
  `summary() -> str` returning `""` when empty else `f"{done}/{len(_TODOS)} done"`
  where `done` counts `status == "completed"`. In `jarvis/tools/todo_write.py`,
  `import` the module and call `todos.set_todos(normalized)` immediately before the
  existing `print_todo_list(normalized)` call (no other behavior change).
  *Verify:* add `jarvis/tests/test_todos.py`: `set_todos([...])` then `get_todos()`
  equals the input but `get_todos() is not` the internal list and mutating the
  returned list/dicts does not change a later `get_todos()`; `clear_todos()` makes
  `get_todos() == []`; `summary()` is `""` when empty and `"1/2 done"` for a
  2-item list with one completed. Extend `test_todo_write.py` to assert that after
  `TodoWriteTool().execute({"todos": [...]})`, `todos.get_todos()` reflects the
  written list. `/selftest` (pytest) green.

- [x] **16.2 `/todos` command to view and clear the maintained list.**
  In `jarvis/commands.py` `handle_command`, add `if cmd == "/todos":` — when
  `arg.strip().lower() == "clear"`, call `todos.clear_todos()` then
  `print_system("Todo list cleared.")` and `return None`; otherwise call
  `formatter.print_todo_list(todos.get_todos())` (which already renders "(no todos)"
  for an empty list) and `return None`. Add `import`s for the `todos` module and
  `print_todo_list`. Register `/todos` in `_HELP_TEXT`, in the `commands_list`
  literal used by `/help`, and in the JARVIS.md command list.
  *Verify:* add a `test_commands.py` case: `todos.set_todos([{"content": "step
  one", "status": "in_progress"}])`, then `handle_command("/todos", ...)` returns
  `None` and (via `capsys`) the output contains `"step one"`; a second call
  `handle_command("/todos clear", ...)` returns `None` and afterwards
  `todos.get_todos() == []`. `/selftest` (pytest) green.

- [x] **16.3 Surface outstanding todos in the system prompt so the agent maintains them.**
  In `jarvis/context.py` `ContextManager.system_message`, after the `_pinned` block
  and before the `_plan_mode` block, `import`/call the `todos` module: when
  `todos.get_todos()` is non-empty, append a `"\n\n## Current Todos\n\n"` section
  listing each item as `- [x] <content>` for `completed` else `- [ ] <content>`
  (with a `(in progress)` suffix for `in_progress`), so every turn the agent re-sees
  its own checklist and keeps working it. Empty list appends nothing.
  *Verify:* add a `test_context.py` case: with `todos.clear_todos()` the
  `system_message["content"]` contains no `"## Current Todos"`; after
  `todos.set_todos([{ "content": "ship it", "status": "pending"}])` the content
  contains `"## Current Todos"` and `"- [ ] ship it"`. Reset the store at test end.
  `/selftest` (pytest) green.

- [x] **16.4 Docs + parity flip.**
  In JARVIS.md, document the `/todos` command in the command list and note that the
  `todo_write` tool now persists the list in a session store (`jarvis/todos.py`),
  recallable with `/todos`, and injected into the system prompt each turn so the
  agent keeps its plan. Flip PARITY.md's "Todo list the agent maintains
  (TaskCreate-style) with live checklist UI" row from ❌ to ✅ (note the panel is a
  full re-render, not an in-place `Live` widget, since a second concurrent `Live`
  would fight the streaming-markdown `Live`).
  *Verify:* `/selftest` (pytest) green; grep confirms the PARITY "Todo list the
  agent maintains" row is no longer ❌ and JARVIS.md mentions `/todos`.

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
