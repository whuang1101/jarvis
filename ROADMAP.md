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

## Phase 17 — `/rewind`: session checkpoints (restore conversation & files)

PARITY row "/rewind (checkpoint & restore conversation + files)" is ❌: once a
turn runs there is no way to step the conversation back to a prior point, and file
edits made by tools can only be reversed by hand or `git`. This phase adds a
session-scoped checkpoint store, an automatic pre-turn snapshot (conversation
history + a `git stash create` of the working tree), and a `/rewind` command to
list checkpoints and restore one. Checkpoints are in-memory (session-scoped, like
`tasks.py`/`todos.py`; they do not survive a restart) and file restore is
best-effort over *tracked* modifications via `git stash create`/`apply` — a
smaller, self-contained cousin of Claude Code's cross-session `/rewind`. No new
Azure calls.

- [x] **17.1 In-memory checkpoint store the REPL writes into.**
  Add `jarvis/checkpoints.py` with a module-level `_CHECKPOINTS: list[dict[str,
  Any]] = []` and `_MAX_CHECKPOINTS = 30`, plus: `create(history: list[dict],
  label: str = "", file_stash: str | None = None) -> int` — appends `{"label":
  label[:80], "history": [dict(m) for m in history], "file_stash": file_stash,
  "time": <ISO-8601 local timestamp>}`, trims the list to its last
  `_MAX_CHECKPOINTS` entries, and returns the 1-based index of the newest entry
  (`len(_CHECKPOINTS)` after trimming); `list_checkpoints() -> list[dict]` — returns
  metadata copies (`label`, `time`, and `has_files = file_stash is not None`), never
  the stored `history`; `get(index: int) -> dict | None` — returns a fresh deep copy
  (`history` re-copied as `[dict(m) for m in ...]`) of the 1-based `index`-th
  checkpoint, or `None` if out of range; `clear() -> None`; and `summary() -> str`
  returning `""` when empty else `f"{len(_CHECKPOINTS)} checkpoints"`. Store the
  internal copy so a later `create` caller mutating the passed-in `history` can't
  change a stored checkpoint.
  *Verify:* add `jarvis/tests/test_checkpoints.py`: `create` returns `1` then `2`
  for two calls; `get(1)["history"]` equals the first input but mutating the returned
  list/dicts does not change a later `get(1)`; passing the same list object to
  `create` and then mutating it afterward leaves the stored checkpoint unchanged;
  `list_checkpoints()` entries carry `label`/`time`/`has_files` and no `history` key;
  more than `_MAX_CHECKPOINTS` calls keeps exactly `_MAX_CHECKPOINTS` (oldest
  dropped); `clear()` empties and `summary()` is `""` when empty. `/selftest`
  (pytest) green.

- [x] **17.2 Git-backed working-tree snapshots.**
  In `jarvis/checkpoints.py` add `snapshot_files(cwd: str | None = None) -> str |
  None`: run `git stash create` (via `subprocess.run`, `capture_output=True,
  text=True`, `cwd=cwd`) and return the stripped stdout SHA when it is non-empty,
  else `None` — swallow every failure (not a git repo, git missing, no changes) and
  return `None`, never raise. Add `restore_files(sha: str, cwd: str | None = None) ->
  str`: run `git stash apply <sha>`; return `"Files restored from checkpoint."` when
  `returncode == 0`, else `f"Error: could not restore files: {stderr.strip()}"`.
  Note in a comment that this covers tracked-file modifications only (`git stash
  create` ignores untracked files).
  *Verify:* add to `test_checkpoints.py` a temp-git-repo case (`git init`, commit a
  tracked file): modify the file, `snapshot_files(cwd=repo)` returns a 40-char SHA;
  `git checkout -- <file>` to discard the change; `restore_files(sha, cwd=repo)`
  returns the success string and the file content is the modified version again.
  A second case: `snapshot_files(cwd=<non-git tmp dir>)` returns `None`. `/selftest`
  (pytest) green.

- [x] **17.3 Auto-checkpoint before each interactive user turn.**
  In `jarvis/checkpoints.py` add `checkpoint_turn(context: "ContextManager", message:
  str) -> int` that calls `create(context._history, label=message,
  file_stash=snapshot_files())` and returns the new index — this captures the
  conversation *before* the new user message is appended, so a rewind returns to the
  pre-turn state. In `jarvis/cli.py`, import the `checkpoints` module and call
  `checkpoints.checkpoint_turn(context, user_input)` immediately before the two
  interactive-REPL `run_agent(...)` dispatch sites for a fresh user turn (the normal
  `run_agent(build_multimodal_content(...))` path and the `_RUN_AGENT_PREFIX` rerun
  path); do NOT add it to the headless `-p` one-shot path in `run_headless`.
  *Verify:* add to `test_checkpoints.py`: build a `ContextManager`, append one
  message, `checkpoint_turn(ctx, "hi")` returns `1` and `get(1)["history"]` has one
  entry with label `"hi"`; append another message, `checkpoint_turn(ctx, "again")`
  returns `2` and `get(2)["history"]` has two entries — the store snapshots the live
  history at call time. Then `grep` confirms `jarvis/cli.py` calls
  `checkpoints.checkpoint_turn`. `/selftest` (pytest) green.

- [x] **17.4 `/rewind` command to list and restore checkpoints.**
  In `jarvis/commands.py` `handle_command`, add `if cmd == "/rewind":` — when
  `arg.strip().lower() == "clear"`, call `checkpoints.clear()` then
  `print_system("Checkpoints cleared.")` and `return None`; when `arg` is a positive
  integer `n`, `cp = checkpoints.get(n)` and if `cp is None` `print_error(f"No
  checkpoint {n}.")` else `context.load_history(cp["history"])`, and if
  `cp["file_stash"]` print the string from `checkpoints.restore_files(cp["file_stash"])`
  (via `print_error` when it starts with `"Error"` else `print_system`), then
  `print_system(f"Rewound to checkpoint {n}.")`, `return None`; otherwise (no arg)
  list — if `checkpoints.list_checkpoints()` is empty `print_system("No checkpoints
  yet.")`, else `print_system` one line per checkpoint as `f"{i}: {label}  ({time})"`
  (1-based `i`, marking `has_files` with a trailing ` [files]`), `return None`. Add
  the `checkpoints` module import. Register `/rewind` in `_HELP_TEXT`, in the
  `commands_list` literal used by `/help`, and in the JARVIS.md command list.
  *Verify:* add a `test_commands.py` case: `checkpoints.clear()`;
  `checkpoints.create([{ "role": "user", "content": "first"}], label="first")`;
  `handle_command("/rewind", ...)` returns `None` and (via `capsys`) output contains
  `"first"`; set `context._history` to a different list, then `handle_command("/rewind
  1", ...)` returns `None` and afterward `context._history == [{"role": "user",
  "content": "first"}]`; `handle_command("/rewind clear", ...)` returns `None` and
  `checkpoints.list_checkpoints() == []`. `/selftest` (pytest) green.

- [x] **17.5 Docs + parity flip.**
  In JARVIS.md, document the `/rewind` command in the command list and note that the
  REPL now snapshots each user turn into a session checkpoint store
  (`jarvis/checkpoints.py`) — conversation history restored in-place and tracked
  file edits restored best-effort via `git stash create`/`apply`. Flip PARITY.md's
  "/rewind (checkpoint & restore conversation + files)" row from ❌ to 🟡 (note:
  session-scoped in-memory checkpoints, not cross-session; file restore covers
  tracked modifications only).
  *Verify:* `/selftest` (pytest) green; grep confirms the PARITY "/rewind" row is no
  longer ❌ and JARVIS.md mentions `/rewind`.

---

## Phase 18 — MCP: runtime add/remove/list + project `.mcp.json` config

PARITY row "MCP: add/remove/list at runtime, project .mcp.json config" is ❌: the
three MCP servers (GitHub / Azure / Brave) are hardcoded in `cli.py:_init_mcp`, the
`MCPManager` is created inline and thrown away (nothing can reach it after startup),
and there is no `/mcp` command and no config file. This phase (1) gives the live
`MCPManager` an inspectable server list, a `disconnect`, and a module-level active
handle; (2) loads extra servers from a Claude-Code-compatible `.mcp.json`
(project + `~/.jarvis/mcp.json` global) at startup; and (3) adds a `/mcp` command to
list, add, and remove servers at runtime. Runtime-added servers are session-scoped
(config-file and hardcoded ones reconnect each launch). No new Azure calls.

- [x] **18.1 MCPManager introspection, disconnect, and an active-manager handle.**
  In `jarvis/mcp_manager.py` add three `MCPManager` methods: `list_servers() ->
  list[dict[str, Any]]` returning `[{"name": name, "tool_count": len(info.get("tools",
  []))} for name, info in self._servers.items()]` sorted by `name`; `disconnect(name:
  str) -> list[str]` — if `name` not in `self._servers` return `[]`, else pop the entry,
  collect its tool names (`[t.name for t in info.get("tools", [])]`), best-effort request
  cancellation of a stored keep-alive task if present (wrap in `try/except`, never raise),
  and return those names. In the `_connect` coroutine, after `ready.set()` and before the
  `await asyncio.Event().wait()`, store the running task on the entry
  (`self._servers[name]["task"] = asyncio.current_task()`) so `disconnect` can tear down
  the stdio subprocess. Add module-level `_ACTIVE_MANAGER: MCPManager | None = None` with
  `set_active_manager(manager)` and `get_active_manager() -> MCPManager | None`. In
  `jarvis/cli.py`, change the `_init_mcp(MCPManager())` call site (~line 282) to build the
  manager into a local, `set_active_manager(mgr)`, then `_init_mcp(mgr)`; add the import.
  *Verify:* add `jarvis/tests/test_mcp_manager.py`: build `MCPManager()`, directly set
  `mgr._servers["srv"] = {"tools": [types.SimpleNamespace(name="a"),
  types.SimpleNamespace(name="b")]}`; assert `list_servers() == [{"name": "srv",
  "tool_count": 2}]`, `disconnect("srv") == ["a", "b"]` and `"srv"` no longer in
  `mgr._servers`, `disconnect("missing") == []`; `set_active_manager(mgr)` then
  `get_active_manager() is mgr` (reset to `None` after). `/selftest` (pytest) green.

- [x] **18.2 Load MCP servers from `.mcp.json` config files.**
  Add `jarvis/mcp_config.py` with `load_mcp_servers(cwd: str | None = None) ->
  list[dict[str, Any]]`: read a global `~/.jarvis/mcp.json` then walk up from `cwd`
  (default `Path.cwd()`) up to `_PROJECT_WALK_DEPTH = 5` levels for a project `.mcp.json`,
  each file shaped `{"mcpServers": {"<name>": {"command": str, "args": [...], "env":
  {...}}}}`. Merge into a dict keyed by server name with project entries overriding global
  ones, and return a list of `{"name": name, "command": command, "args": args or [],
  "env": env or {}}` for every entry with a non-empty `command`. Best-effort: a missing
  file, unreadable file, JSON/parse error, or non-dict shape skips that file and never
  raises; an entry without `command` is dropped. Expose the global path as a module
  constant (e.g. `_GLOBAL_CONFIG`) so tests can monkeypatch it. In `jarvis/cli.py`
  `_init_mcp`, after the three hardcoded server blocks, loop over `load_mcp_servers()` and
  call `_connect_mcp(mcp, entry["name"], entry["command"], entry["args"], entry["env"])`
  for each.
  *Verify:* add `jarvis/tests/test_mcp_config.py` (monkeypatch `_GLOBAL_CONFIG` to a temp
  path): a temp `.mcp.json` with two well-formed servers → `load_mcp_servers(cwd=tmp)`
  returns both with correct `command`/`args`/`env`; an entry missing `command` is dropped;
  a project entry overrides a global entry of the same name; a malformed-JSON file returns
  `[]` without raising. `/selftest` (pytest) green.

- [x] **18.3 `unregister_tool` + `/mcp` command (list / add / remove).**
  In `jarvis/tools/__init__.py` add `unregister_tool(name: str) -> None` that deletes
  `_BY_NAME.pop(name, None)` and rebuilds `_REGISTRY` without any tool whose `.name ==
  name`. In `jarvis/commands.py:handle_command`, add a `/mcp` branch (import
  `get_active_manager` from `.mcp_manager` and `register_tool`/`unregister_tool` from
  `.tools`): parse the argument string — no arg or `list` → `mgr = get_active_manager()`;
  if `None` emit a "no MCP manager active (start with --mcp)" line, else if
  `mgr.list_servers()` is empty emit "No MCP servers connected." else one line per server
  as `f"{name} — {tool_count} tools"`; `add <name> <command> [args...]` → on too few tokens
  emit a usage error, else `try` `tools = mgr.connect(name=name, command=command,
  args=args, env={})`, `register_tool` each, emit `f"Connected {name} ({len(tools)}
  tools)."`, catching `Exception as e` → `f"Error: could not connect {name}: {e}"`;
  `remove <name>` → `names = mgr.disconnect(name)`, `unregister_tool` each, emit
  `f"Removed {name} ({len(names)} tools)."` when `names` else `f"Error: no MCP server
  named {name}."`. All output through `formatter` helpers (`print_command_output` for
  listings, `print_error` for the `"Error: ..."` lines); every path `return None`. Register
  `/mcp` in `_HELP_TEXT`, in the `commands_list` literal used by `/help`, and in the
  JARVIS.md command list.
  *Verify:* add a `test_commands.py` case: build a fake manager
  (`types.SimpleNamespace`) whose `list_servers()` returns `[{"name": "srv", "tool_count":
  3}]`, `connect(...)` returns `[]`, and `disconnect(name)` returns `["x"]`;
  `mcp_manager.set_active_manager(fake)`; `handle_command("/mcp", ...)` returns `None` and
  (via `capsys`) output contains `"srv"` and `"3"`; `handle_command("/mcp remove srv",
  ...)` returns `None` and output contains `"Removed srv"`; reset
  `set_active_manager(None)` after. `/selftest` (pytest) green.

- [x] **18.4 Docs + parity flip.**
  In JARVIS.md, document the `/mcp` command in the command list (list/add/remove connected
  MCP servers) and note that extra MCP servers can be declared in a project `.mcp.json`
  or global `~/.jarvis/mcp.json` (`{"mcpServers": {name: {command, args, env}}}`) and are
  connected at startup alongside the built-in GitHub/Azure/Brave servers. Flip PARITY.md's
  "MCP: add/remove/list at runtime, project .mcp.json config" row from ❌ to 🟡 (note:
  `/mcp` list/add/remove + `.mcp.json` startup loading; runtime-added servers are
  session-scoped).
  *Verify:* `/selftest` (pytest) green; grep confirms the PARITY MCP-runtime row is no
  longer ❌ and JARVIS.md mentions `/mcp` and `.mcp.json`.

---

## Phase 19 — Vision input: read images as visual content

> PARITY.md's topmost genuinely-missing feature: "Read images (vision input)". Jarvis
> can read text/PDF/notebooks but silently has no path for image files — a `read_file`
> on a `.png` would just try to decode bytes as text. This phase lets the agent *see*
> an image the user points it at by attaching it to the model conversation as an
> `image_url` content part (the OpenAI/Azure multimodal shape). The actual model call
> needs a vision-capable Azure deployment, but every step here is verified offline with
> pytest — we test the encoding/message construction, not a live completion.

- [x] **19.1 Image encoding helpers (`jarvis/images.py`).**
  Add a new module `jarvis/images.py` with: a `frozenset` constant `_IMAGE_EXTENSIONS =
  {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}`; `is_image_path(path: str) -> bool`
  that lower-cases `path` and returns whether it ends with any extension in the set;
  `_mime_for(path: str) -> str` mapping the extension to a MIME type (`.jpg`/`.jpeg` →
  `image/jpeg`, `.png` → `image/png`, `.gif` → `image/gif`, `.webp` → `image/webp`,
  `.bmp` → `image/bmp`, default `application/octet-stream`); `encode_image_data_url(path:
  str) -> str` that reads the file bytes, base64-encodes them, and returns
  `f"data:{_mime_for(path)};base64,{b64}"`; `image_content_part(path: str) -> dict` that
  returns `{"type": "image_url", "image_url": {"url": encode_image_data_url(path)}}`; and
  `image_message(path: str) -> dict` returning a user message
  `{"role": "user", "content": [{"type": "text", "text": f"Here is the image {path}:"},
  image_content_part(path)]}`. Pure functions, no imports from other jarvis modules.
  *Verify:* add `jarvis/tests/test_images.py`: `is_image_path("a/b/Photo.PNG")` and
  `is_image_path("x.jpg")` are `True`, `is_image_path("notes.txt")` is `False`; write a
  tiny temp `.png` (a few bytes) and assert `encode_image_data_url(tmp)` starts with
  `"data:image/png;base64,"`; `image_content_part(tmp)["image_url"]["url"]` equals that
  data URL; `image_message(tmp)` has `role == "user"`, its `content[0]["type"] == "text"`
  and `content[1]["type"] == "image_url"`. `/selftest` (pytest) green.

- [x] **19.2 `vision` setting (default on).**
  In `jarvis/settings.py` add a field `vision: bool = True` to the `Settings` dataclass
  (alongside `show_thinking`); because `scalar_keys` is derived from `fields(cls)` it is
  picked up by the `~/.jarvis/config.toml` + project `.jarvis.toml` overlay automatically —
  no other settings-loading change needed. Document the `vision` key in JARVIS.md's
  settings/config section (one line: "`vision` (bool, default true) — attach image files
  read with `read_file` to the conversation as visual input; set false to disable").
  *Verify:* add to `jarvis/tests/test_settings.py` (or a new `test_settings_vision`):
  `Settings().vision is True`; write a temp global TOML containing `vision = false` and
  assert `Settings.load(path=tmp).vision is False`. `/selftest` (pytest) green.

- [x] **19.3 `read_file` recognises image files.**
  In `jarvis/tools/read_file.py`, after the sensitive-path guard and before the
  `os.path.getsize` size check, add `from ..images import is_image_path` and a branch:
  when `is_image_path(path)`, first confirm the file exists (`os.path.exists(path)`,
  returning `f"Error: file not found: {path}"` if not), then read `jarvis.settings`'s
  `vision` flag via `from ..settings import Settings; Settings.load().vision` — if vision
  is off, return the plain string `f"Note: {path} is an image; vision is disabled (set
  vision = true in config to view it)."`; if vision is on, return the plain marker string
  `f"[Image {path} attached below as visual input.]"`. This keeps the tool contract
  (returns a plain string); the actual attachment happens in 19.4. Update JARVIS.md's tool
  table row for `read_file` to note it now recognises image files and attaches them as
  visual input when `vision` is enabled.
  *Verify:* add to `jarvis/tests/test_read_file.py`: writing a temp `photo.png` and calling
  `ReadFileTool().execute({"path": tmp})` returns a string containing `"attached below"`
  by default; monkeypatching so vision is off returns a string containing `"vision is
  disabled"`; a `.png` path that does not exist returns `"Error: file not found"`.
  `/selftest` (pytest) green.

- [x] **19.4 Agent attaches the image after the tool result.**
  In `jarvis/agent.py`, import `from .images import is_image_path, image_message` at the
  top. In the tool-result loop, immediately after the existing `context.append({"role":
  "tool", "tool_call_id": tc["id"], "content": result})`, add: if `_settings.vision` and
  `tool_name == "read_file"` and `is_image_path(str(args.get("path", "")))` and the result
  does not start with `"Error"`, then `context.append(image_message(str(args["path"])))` so
  the encoded image is sent to the model on the next turn. Flip PARITY.md's "Read images
  (vision input)" row from ❌ to ✅ with a note (`read_file` image detection + `image_url`
  attachment, gated by `vision` setting).
  *Verify:* add `jarvis/tests/test_vision_agent.py` (or extend an agent test): a small test
  that builds a `read_file` image scenario and asserts the appended message — construct the
  message directly via `image_message("pic.png")` and assert it is a `user` message whose
  second content part is an `image_url` (the wiring in `agent.py` calls exactly this
  helper); plus a `grep`-style assertion is unnecessary — instead assert the branch guard
  logic by checking `is_image_path("pic.png") is True` and `is_image_path("x.py") is
  False`. `/selftest` (pytest) green; grep confirms `agent.py` references `image_message`
  and the PARITY "Read images (vision input)" row is no longer ❌.

---

## Phase 20 — MCP reconnect on crash

> PARITY.md's topmost genuinely-missing, cleanly-feasible feature: "MCP reconnect on
> crash". Today `MCPManager._call_tool` awaits `session.call_tool` against a long-lived
> stdio subprocess; if that server has died (crashed, killed, OOM) the call raises and
> the tool is dead for the rest of the session with no recovery. This phase makes a
> failed MCP tool call transparently tear down and re-spawn the server once, then retry,
> gated by a new `mcp_auto_reconnect` setting (default on). Every step is verified
> offline with pytest by monkeypatching `MCPManager`'s spawn/run seams — we test the
> reconnect plumbing, not a live MCP server (which would need `gh`/Azure/Brave auth).

- [x] **20.1 Record spawn params and add a `reconnect` seam (`jarvis/mcp_manager.py`).**
  In `MCPManager.__init__` add `self._server_params: dict[str, dict[str, Any]] = {}`.
  At the top of `connect(name, command, args, env)` — synchronously, before spawning the
  `_connect` coroutine — record `self._server_params[name] = {"command": command,
  "args": list(args), "env": dict(env)}` so a later crash that pops `self._servers[name]`
  does not lose the parameters needed to respawn. Add a method
  `reconnect(self, name: str) -> bool`: if `name not in self._server_params` return
  `False`; call `self.disconnect(name)` (ignore its return), then in a `try` re-establish
  the server with `self.connect(name, **self._server_params[name])` and return `True`;
  on any `Exception` return `False`. Because `connect` re-records params and repopulates
  `self._servers[name]`, a successful `reconnect` leaves a fresh session in place.
  *Verify:* add `jarvis/tests/test_mcp_reconnect.py`: construct an `MCPManager()`,
  monkeypatch `mgr.connect` with a stub that records `(name, kwargs)` and returns `[]`;
  seed `mgr._server_params["srv"] = {"command": "c", "args": [], "env": {}}` and assert
  `mgr.reconnect("srv") is True` and the stub was called once with `name == "srv"` and
  the stored `command`/`args`/`env`; assert `mgr.reconnect("missing") is False`; then
  monkeypatch `mgr.connect` to raise and assert `mgr.reconnect("srv") is False`.
  `/selftest` (pytest) green.

- [x] **20.2 Retry a failed MCP tool call once via reconnect.**
  In `jarvis/settings.py` add `mcp_auto_reconnect: bool = True` to the `Settings`
  dataclass (alongside `vision`); it is auto-picked-up by the config overlay because
  `scalar_keys` derives from `fields(cls)`. In `jarvis/mcp_manager.py._call_tool`, wrap
  the existing `return self._run(_call(), timeout=60)` in a `try`; on `Exception as exc`,
  read `from .settings import Settings` and if `Settings.load().mcp_auto_reconnect` and
  `self.reconnect(server_name)` returns `True`, `return self._run(_call(), timeout=60)`
  once more (the retry; `_call` reads `self._servers[server_name]["session"]` at call
  time so it uses the fresh session); otherwise
  `return f"Error: MCP tool '{tool_name}' on '{server_name}' failed and could not
  reconnect: {exc}"`. Keep the tool contract (plain string, `"Error: ..."` on failure).
  *Verify:* extend `jarvis/tests/test_mcp_reconnect.py`: monkeypatch `mgr._run` to raise
  on its first call and return `"ok"` on the second, monkeypatch `mgr.reconnect` to
  record a call and return `True`, and assert `mgr._call_tool("srv", "t", {})` returns
  `"ok"` with `reconnect` called exactly once; then with `mgr.reconnect` returning
  `False` assert the result starts with `"Error:"`; then with a temp global TOML setting
  `mcp_auto_reconnect = false` (loaded via `Settings.load(path=tmp)` monkeypatched in)
  assert `_call_tool` returns an `"Error:"` string without calling `reconnect`.
  `/selftest` (pytest) green.

- [x] **20.3 Docs + parity flip.**
  In `JARVIS.md`, add `mcp_auto_reconnect` to the runtime-settings section (one line:
  "`mcp_auto_reconnect` (bool, default true) — if an MCP tool call fails because its
  stdio server died, transparently respawn the server and retry the call once") and add
  a sentence to the `### MCP integration (mcp_manager.py)` section noting that
  `_call_tool` reconnects-and-retries once on failure. In `PARITY.md` flip the "MCP
  reconnect on crash" row from ❌ to ✅ with the note "transparent respawn + single retry
  in `_call_tool`, gated by `mcp_auto_reconnect`".
  *Verify:* `grep` confirms `mcp_manager.py` defines `def reconnect` and that `_call_tool`
  references `reconnect`; `grep` confirms `JARVIS.md` mentions `mcp_auto_reconnect` and
  the PARITY "MCP reconnect on crash" row is no longer ❌. `/selftest` (pytest) green.

---

## Phase 21 — Prompt caching / cost optimization

Azure OpenAI applies automatic prompt caching to repeated prompt prefixes (the stable
system prompt + tool schemas + prior turns) and reports the cached slice as
`usage.prompt_tokens_details.cached_tokens`. Cached input tokens bill at a discount, so
surfacing them makes `/usage` cost estimates accurate and gives the user visibility into
cache effectiveness. This phase threads that field through the usage tracker, the read
paths, and the displays — no request-shape changes, since the prompt prefix is already
stable across turns.

- [x] **21.1 UsageTracker records cached tokens and discounts their cost.**
  In `jarvis/context.py` `UsageTracker`: add `self.cached_tokens: int = 0` in `__init__`,
  and change `record(self, prompt, completion, deployment="")` to
  `record(self, prompt, completion, deployment="", cached=0)`. In the body,
  `self.cached_tokens += cached` (treat `cached` as a subset of `prompt`), and change the
  cost line so cached input tokens bill at half rate:
  `self.cost_usd += ((prompt - cached) * inp + cached * inp * 0.5 + completion * out) / 1_000_000`.
  Keep the `if deployment:` guard. Do not change any callers in this step (the new
  parameter defaults to `0`, so existing calls behave identically).
  *Verify:* extend `jarvis/tests/test_context.py` (or add it) with a test that builds a
  `UsageTracker`, calls `record(1000, 200, "gpt-4o", cached=800)`, and asserts
  `tracker.cached_tokens == 800`, `tracker.prompt_tokens == 1000`, and that `cost_usd`
  equals `((200 * inp) + (800 * inp * 0.5) + 200 * out) / 1_000_000` for the looked-up
  `gpt-4o` price; and a second call with no `cached=` arg leaves `cached_tokens`
  unchanged from its prior value. `/selftest` (pytest) green.

- [x] **21.2 Thread cached_tokens through the streaming and non-streaming read paths.**
  In `jarvis/client.py`: add `cached_tokens: int` to the `CompleteResult` NamedTuple
  (after `completion_tokens`), and in `complete()` set it from
  `getattr(getattr(usage, "prompt_tokens_details", None), "cached_tokens", 0) or 0` when
  `usage` else `0`. In `jarvis/agent.py` around line 198, read the same nested field off
  `chunk.usage` into a local (guarding `None`) and pass it as the new `cached=` argument
  to `tracker.record(...)`. In `jarvis/context.py` around line 284, pass
  `cached=result.cached_tokens` to `tracker.record(...)` in the compaction path.
  *Verify:* add a test in `jarvis/tests/test_agent.py` (or existing streaming test) that
  feeds a fake chunk whose `usage` has `prompt_tokens=1000, completion_tokens=100` and a
  `prompt_tokens_details.cached_tokens=600` (use `types.SimpleNamespace`), drains it, and
  asserts `tracker.cached_tokens == 600`; and a chunk whose `usage` lacks
  `prompt_tokens_details` records `cached_tokens == 0` without error. `/selftest` green.

- [x] **21.3 Surface cached tokens in `/usage` and the headless JSON result.**
  In `jarvis/commands.py` `/usage` (around line 332), add a line after "Prompt tokens":
  `f"  Cached (of prompt): [cyan]{tracker.cached_tokens:>10,}[/cyan]  [dim]({pct}% hit)[/dim]\n"`
  where `pct = round(100 * tracker.cached_tokens / tracker.prompt_tokens)` if
  `tracker.prompt_tokens` else `0`. In `jarvis/cli.py` around line 246, add
  `"cached_input_tokens": tracker.cached_tokens,` to the `usage` dict in the JSON result.
  *Verify:* add/extend a test asserting the `-p --output-format json` result dict's
  `usage` contains `cached_input_tokens`; and a `commands.py` test (or manual grep) that
  the `/usage` handler references `tracker.cached_tokens`. `/selftest` green.

- [x] **21.4 Docs + parity flip.**
  In `JARVIS.md`, note in the usage/cost section (or `UsageTracker` mention) that Jarvis
  tracks Azure's `cached_tokens` and bills cached input at half rate, shown in `/usage`
  and the headless JSON `usage.cached_input_tokens`. In `PARITY.md` flip the
  "Prompt caching / cost optimization" row from ❌ to 🟡 with the note
  "surfaces Azure `cached_tokens` in `/usage` + JSON, cost discounted; relies on Azure's
  automatic prefix caching (no explicit cache-control API)".
  *Verify:* `grep` confirms `context.py` defines `cached_tokens`, `client.py`
  `CompleteResult` includes `cached_tokens`, and `commands.py` references
  `tracker.cached_tokens`; `grep` confirms `JARVIS.md` mentions `cached_tokens` and the
  PARITY "Prompt caching" row is no longer ❌. `/selftest` (pytest) green.

---

## Phase 22 — Sandboxed command execution

`run_command` currently runs shell commands with `shell=True` at full user privilege —
the only guard is the permission gate. Claude Code offers a sandbox that isolates command
network + filesystem access so risky commands can run without a prompt. On Linux the
standard primitive is `bwrap` (bubblewrap): it runs the command in a new namespace with a
read-only view of the root filesystem, a writable bind of the project directory, a private
`/tmp`, and (optionally) no network. This phase adds an opt-in sandbox that wraps commands
in `bwrap` when enabled, deny-by-default if `bwrap` is unavailable, toggleable per session
via `/sandbox`. No change to command semantics when the sandbox is off (default).

- [x] **22.1 Sandbox setting + runtime toggle state.**
  In `jarvis/settings.py` `Settings`: add two scalar fields — `sandbox: bool = False` and
  `sandbox_allow_network: bool = False` (they load automatically as scalar keys; no
  `_TABLE_KEYS` change). In `jarvis/permissions.py`, mirror the `auto_mode` pattern: add a
  module-level `_sandbox: bool = _settings.sandbox` and functions `is_sandbox() -> bool`
  (returns `_sandbox`) and `set_sandbox(enabled: bool) -> None` (`global _sandbox`; assign).
  *Verify:* a `settings.py` test asserts `Settings().sandbox is False` and
  `Settings().sandbox_allow_network is False`, and that a `.jarvis.toml` containing
  `sandbox = true` loads as `sandbox is True`; a `permissions.py` test asserts
  `set_sandbox(True)` then `is_sandbox()` is `True` (reset to `False` after). `/selftest` green.

- [x] **22.2 Pure sandbox-argv builder.**
  In `jarvis/tools/run_command.py` add a module-level helper
  `_build_sandbox_argv(command: str, cwd: str, allow_network: bool) -> list[str]` that
  returns the `bwrap` argv: start with `[bwrap_path, "--ro-bind", "/", "/", "--dev",
  "/dev", "--proc", "/proc", "--tmpfs", "/tmp", "--bind", cwd, cwd, "--chdir", cwd,
  "--die-with-parent"]`, append `"--unshare-net"` when `not allow_network`, then
  `["/bin/sh", "-c", command]`. Resolve `bwrap_path` via `shutil.which("bwrap")`; if it is
  `None`, return an empty list to signal "unavailable". Do not call this from `execute` yet.
  *Verify:* a test that monkeypatches `shutil.which` to return `"/usr/bin/bwrap"` asserts
  the argv contains `"--unshare-net"` when `allow_network=False` and omits it when `True`,
  binds `cwd` read-write (`"--bind", cwd, cwd` present), and ends with
  `["/bin/sh", "-c", command]`; a test with `which` returning `None` asserts `[]`. `/selftest` green.

- [x] **22.3 Wire the sandbox into `execute`, deny-by-default when unavailable.**
  In `run_command.py` `execute`, after the `cd`/`background` short-circuits and before the
  `subprocess.Popen`: import `is_sandbox` from `..permissions`; when `is_sandbox()` is true,
  call `_build_sandbox_argv(command, os.getcwd(), Settings.load().sandbox_allow_network)`.
  If it returns `[]`, return the string
  `"Error: sandbox is enabled but 'bwrap' was not found on PATH; install bubblewrap or run /sandbox off"`.
  Otherwise run that argv with `shell=False` (pass the list as `command` to `Popen`, drop
  `shell=True` for the sandboxed branch) keeping the existing streaming/timeout logic; the
  non-sandboxed branch is unchanged.
  *Verify:* a test with `is_sandbox` monkeypatched true and `shutil.which("bwrap")` → `None`
  asserts `execute({"command": "echo hi"})` returns the `bwrap`-not-found `Error:` string; a
  test with the sandbox off confirms `echo sandbox_off_marker` still runs and its stdout
  appears (unchanged path). `/selftest` green.

- [x] **22.4 `/sandbox` slash command.**
  In `jarvis/commands.py` `handle_command()`, add a `/sandbox [on|off|status]` branch:
  no arg or `status` prints the current state via a `formatter.py` helper; `on`/`off` call
  `permissions.set_sandbox(True/False)` and print confirmation; every branch `return`s. Add
  the `/sandbox` line to `_HELP_TEXT`, and add it to the command list in `JARVIS.md`.
  *Verify:* a `commands.py` test drives `handle_command("/sandbox on")` then asserts
  `permissions.is_sandbox()` is `True`, `handle_command("/sandbox off")` → `False`, and
  `handle_command("/sandbox")` returns without raising; `grep` confirms `_HELP_TEXT` and
  `JARVIS.md` mention `/sandbox`. `/selftest` green.

- [x] **22.5 Docs + parity flip.**
  In `JARVIS.md`, document the sandbox in the settings/config section: `sandbox` and
  `sandbox_allow_network` keys, `bwrap` requirement, deny-by-default behavior, and the
  `/sandbox` toggle. In `PARITY.md`, flip the "Sandboxed command execution" row from ❌ to
  🟡 with the note "opt-in `bwrap` sandbox (read-only root, writable project dir, net off by
  default); Linux-only, deny-by-default when bwrap missing; `/sandbox` toggle".
  *Verify:* `grep` confirms `JARVIS.md` mentions `sandbox` and `/sandbox`, and the PARITY
  "Sandboxed command execution" row is no longer ❌. `/selftest` (pytest) green.

---

## Phase 23 — Skills (auto-triggered markdown capabilities)

Jarvis already loads user-authored slash commands from markdown (Phase 4.1), but those
only fire when the user types `/name`. Claude Code's *skills* go further: a folder of
markdown capabilities, each with a short `description`, whose names + descriptions are
surfaced to the model so it can decide on its own when a capability is relevant and pull
in the full instructions. The token-efficient shape is: the system prompt carries only a
cheap catalog (name + one-line description per skill), and the model loads a skill's full
body on demand through a `skill` tool. This phase adds skill discovery from
`~/.jarvis/skills/` (global) and `<project>/.jarvis/skills/` (project, shadowing global by
name), a prompt catalog, the on-demand `skill` tool, and a `/skills` command to list them.
No behavior change when no skills are present.

- [x] **23.1 Skill discovery + frontmatter parsing (`jarvis/skills.py`).**
  New module `jarvis/skills.py`. A skill lives at either `<dir>/<name>.md` or
  `<dir>/<name>/SKILL.md`, under `~/.jarvis/skills/` (global) and `Path.cwd()/.jarvis/skills/`
  (project). Define a frozen `Skill` dataclass (`name: str`, `description: str`, `body: str`,
  `path: Path`). Add a private `_parse(path)` that reads the file, strips a leading
  `---`-fenced YAML-ish frontmatter block, pulls `name:` and `description:` via simple
  `key: value` line splitting (fall back to the file/dir stem for `name`, `""` for
  `description`), and treats the text after the frontmatter as `body`. Expose
  `discover_skills() -> list[Skill]` (project entries override global ones with the same
  `name`, returned sorted by name) and `load_skill(name) -> Skill | None`.
  *Verify:* a test writes a temp global dir + project dir (monkeypatching `Path.home` and
  `cwd`), and asserts `discover_skills()` parses `name`/`description`/`body`, that a project
  skill shadows a same-named global one, and that `load_skill("missing")` returns `None`.
  `/selftest` green.

- [x] **23.2 Inject the skills catalog into the system prompt (`jarvis/context.py`).**
  In `ContextManager.system_message`, after the project-context block, import
  `discover_skills` from `.skills` and, when it returns a non-empty list, append a
  `## Skills` section: one `- <name>: <description>` line per skill, followed by a single
  instruction line telling the model to call the `skill` tool with a skill's `name` to load
  its full instructions before acting on it. Append nothing when there are no skills (prompt
  byte-identical to today).
  *Verify:* a test monkeypatches `context.discover_skills` to return one fake `Skill` and
  asserts the rendered `system_message["content"]` contains the skill name, its description,
  and the word `skill` (the tool-name instruction); a second test with `discover_skills`
  returning `[]` asserts no `## Skills` header appears. `/selftest` green.

- [x] **23.3 On-demand `skill` tool (`jarvis/tools/skill.py` + registry).**
  New `SkillTool(BaseTool)` with `name = "skill"`, a description explaining it loads a named
  skill's full instructions, and a `parameters` schema with one required string `name`.
  `execute` calls `load_skill(args["name"])` and returns the skill `body`, or
  `"Error: no skill named '<name>'"` when it is missing. Register it in
  `jarvis/tools/__init__.py` (`import` + `_REGISTRY` entry) and add a row to the tool table
  in `JARVIS.md`.
  *Verify:* a test monkeypatches `load_skill` to return a fake `Skill` and asserts
  `SkillTool().execute({"name": "x"})` returns its body; with `load_skill` → `None` it
  returns the `no skill named` `Error:` string; a registry test confirms a tool named
  `skill` is present. `/selftest` green.

- [x] **23.4 `/skills` slash command (`jarvis/commands.py`).**
  In `handle_command()`, add a `/skills` branch: call `skills.discover_skills()` and print,
  via a `formatter.py` helper (`print_system` is fine), one `<name> — <description>` line per
  skill, or a "No skills found" message when empty; the branch must `return`. Add the
  `/skills` line to `_HELP_TEXT`, and add `/skills` to the command list in `JARVIS.md`.
  *Verify:* a `commands.py` test writes a temp skill and asserts `handle_command("/skills")`
  returns without raising and its captured output mentions the skill name; `grep` confirms
  `_HELP_TEXT` and `JARVIS.md` mention `/skills`. `/selftest` green.

- [x] **23.5 Docs + parity flip.**
  In `JARVIS.md`, document skills in the extensibility/config section: the two skill
  directories, the `<name>.md` / `<name>/SKILL.md` layout with `name` + `description`
  frontmatter, how the catalog is injected into the system prompt, the `skill` tool for
  on-demand loading, and the `/skills` command. In `PARITY.md`, flip the "Skills (folder of
  markdown capabilities, auto-triggered)" row from ❌ to 🟡 with the note "name+description
  catalog injected into the system prompt from `~/.jarvis/skills/` + project `.jarvis/skills/`;
  model loads full body on demand via the `skill` tool; `/skills` lists them".
  *Verify:* `grep` confirms `JARVIS.md` mentions `skill`/`/skills` and the PARITY "Skills"
  row is no longer ❌. `/selftest` (pytest) green.

---

## Phase 24 — Status line customization

The input-bar top border (`╭─ ~/jarvis · 0.0k tokens ───╮`, built inline in
`jarvis/cli.py:main()` and drawn by `_read_input`) is the only status surface Jarvis
exposes, and its contents are hard-coded. Claude Code lets users customize this line by
configuring a shell command that renders it. This phase adds a `statusline` setting: when
set, Jarvis runs it as a shell command each prompt, feeds it a small JSON payload
(cwd, tokens, mode flags) on stdin, and uses the command's first stdout line as the
status text — falling back to the built-in default on empty output, non-zero exit, or
timeout. A `/statusline` command views/sets/clears it. No behavior change when the
setting is empty (the default today).

- [x] **24.1 Extract the default status builder (`jarvis/status.py`).**
  New module `jarvis/status.py`. Add a pure function
  `build_default_status(cwd: Path, tokens: int, plan: bool, auto: bool, danger: bool) -> str`
  that reproduces today's inline string exactly: `~`-abbreviated cwd (relative to
  `Path.home()`, falling back to the absolute path), ` · {tokens/1000:.1f}k tokens`, then
  ` · PLAN` / ` · AUTO` / ` · DANGER` suffixes for each true flag. Replace the inline status
  construction in `jarvis/cli.py:main()` (the `status = f"{short} · ..."` block) with a call
  to `build_default_status(...)`. Pure refactor, no behavior change.
  *Verify:* a `status` test asserts `build_default_status` returns the expected string for a
  known cwd/token count with each combination of flags off and all on (checking the
  ` · PLAN · AUTO · DANGER` ordering); `/selftest` green.

- [x] **24.2 Add the `statusline` setting (`jarvis/settings.py`).**
  Add a scalar field `statusline: str = ""` to the `Settings` dataclass (it is a top-level
  scalar, so it is picked up automatically by `load` / `persist_setting`, not a `_TABLE_KEYS`
  entry). Document the new key in the JARVIS.md settings/config section (1-line table row or
  bullet).
  *Verify:* a `settings` test writes a temp `config.toml` containing
  `statusline = "echo hi"` and asserts `Settings.load(path=...)` yields
  `statusline == "echo hi"`, and that the default (no key) is `""`; `grep` confirms
  `statusline` is documented in JARVIS.md; `/selftest` green.

- [x] **24.3 Render a custom status via the configured command (`jarvis/status.py`).**
  Add `render_status(settings: Settings, cwd: Path, tokens: int, plan: bool, auto: bool,
  danger: bool) -> str`. When `settings.statusline` is empty, return
  `build_default_status(...)`. Otherwise run it with
  `subprocess.run(settings.statusline, shell=True, input=<json>, capture_output=True,
  text=True, timeout=...)`, passing a JSON object with `cwd` (str), `tokens` (int), `plan`,
  `auto`, `danger` on stdin; on a zero exit with non-empty stdout, return the first stdout
  line stripped; on empty output, non-zero exit, `TimeoutExpired`, or any exception, fall
  back to `build_default_status(...)`. Wire `render_status` into `jarvis/cli.py:main()` in
  place of the 24.1 `build_default_status` call (loading `Settings` as `main` already does /
  via `Settings.load`).
  *Verify:* a `status` test monkeypatches `subprocess.run` to return a stub with
  `returncode=0, stdout="CUSTOM\n"` and asserts `render_status` (with a non-empty
  `statusline`) returns `"CUSTOM"`; a second case where `subprocess.run` raises
  `TimeoutExpired` (or returns `returncode=1`) asserts it returns the default status; with an
  empty `statusline` it returns the default without invoking the command; `/selftest` green.

- [x] **24.4 `/statusline` slash command (`jarvis/commands.py`).**
  In `handle_command()`, add a `/statusline` branch modeled on `/theme`: no arg prints the
  current `statusline` value (or "(default)" when empty) via a `formatter.py` helper;
  `/statusline off` clears it (`persist_setting("statusline", "")`); any other arg persists it
  verbatim via `persist_setting("statusline", arg)` and confirms with `print_system`; the
  branch must `return`. Add a `/statusline` line to `_HELP_TEXT` and to the command list in
  JARVIS.md.
  *Verify:* a `commands.py` test calls `handle_command("/statusline")` and asserts it returns
  without raising and its captured output mentions "status"; `grep` confirms `_HELP_TEXT` and
  JARVIS.md mention `/statusline`; `/selftest` green.

- [x] **24.5 Docs + parity flip.**
  In JARVIS.md, document status-line customization in the extensibility/config section: the
  `statusline` setting, the command-based hook (runs each prompt, JSON payload of
  cwd/tokens/mode flags on stdin, first stdout line becomes the input-bar top-border status,
  falls back to the built-in default on empty/error/timeout), and the `/statusline` command.
  In PARITY.md, flip the "Status line customization" row from ❌ to 🟡 with the note "shell
  command in `statusline` setting; receives cwd/tokens/mode JSON on stdin, first stdout line
  becomes the input-bar top border, falls back to default on error; `/statusline` sets it".
  *Verify:* `grep` confirms JARVIS.md mentions `statusline`/`/statusline` and the PARITY
  "Status line customization" row is no longer ❌; `/selftest` (pytest) green.

---

## Phase 25 — PR creation with generated title/body (`/pr`)

Parity gap: "PR creation with generated title/body" is ❌. Jarvis already has `/commit`
(stage + agent-authored commit) and `/review` (agent reviews a diff). Add a `/pr` slash
command that gathers the branch's context and hands the agent a prompt to write a PR title
and body and run `gh pr create`, mirroring the `_RUN_AGENT_PREFIX` pattern those commands use.

- [x] **25.1 PR-context helper (`jarvis/commands.py`).**
  Add a module-level helper `def _pr_context() -> tuple[str | None, str | None]:` returning
  `(context, error)` — exactly one non-`None`. It runs, each via
  `subprocess.run(..., capture_output=True, text=True, timeout=30)` inside a `try/except`
  that maps `subprocess.TimeoutExpired` to `(None, "Building the PR context timed out.")` and
  any other `Exception` to `(None, f"Failed to build PR context: {e}")`:
  `git rev-parse --abbrev-ref HEAD` (branch), `git log main..HEAD --pretty=format:%s`
  (commit subjects), and `git diff main...HEAD` (diff). If the branch is `main`, return
  `(None, "You are on main — check out a feature branch before opening a PR.")`; if the diff
  is empty, return `(None, "No commits on this branch to open a PR for.")`. On success return
  a context string embedding the branch, the commit-subject list, and the diff in a
  ```` ```diff ```` fence, error `None`.
  *Verify:* a `commands.py` test monkeypatches `subprocess.run` to report branch
  `feat/x` with a non-empty diff and asserts `_pr_context()` returns `(ctx, None)` with `ctx`
  containing `feat/x`; a second case where the branch is `main` asserts the error mentions
  "main" and context is `None`; a third where the diff is empty asserts the error mentions
  "No commits". `/selftest` (pytest) green.

- [x] **25.2 Wire the `/pr` command (`jarvis/commands.py`).**
  In `handle_command()`, add a `/pr` branch (near `/commit`/`/review`): call `_pr_context()`;
  on error, `print_error(error)` and `return None`; otherwise return
  `f"{_RUN_AGENT_PREFIX}{message}"` where `message` embeds the context and instructs the agent
  to write a concise PR title and body (why, not just what) and run
  `gh pr create --title "<title>" --body "<body>"` (so the call goes through the normal tool
  permission gate). The branch must `return`. Add a `/pr` line to `_HELP_TEXT` and add `"/pr"`
  to the autocomplete `commands_list` (near `"/commit"`/`"/review"`).
  *Verify:* a `commands.py` test monkeypatches `_pr_context` to return `("CTX", None)` and
  asserts `handle_command("/pr")` returns a string starting with `_RUN_AGENT_PREFIX` that
  contains `gh pr create` and `CTX`; a second test where `_pr_context` returns
  `(None, "boom")` asserts `handle_command("/pr")` returns `None` and the captured output
  mentions "boom". `grep` confirms `_HELP_TEXT` and the autocomplete list mention `/pr`.
  `/selftest` (pytest) green.

- [x] **25.3 Docs + parity flip (`JARVIS.md`, `PARITY.md`).**
  In JARVIS.md, add `/pr` to the `Implemented commands:` list and document it beside
  `/commit`/`/review`: it collects the branch, commit subjects, and `git diff main...HEAD`,
  then has the agent author a title/body and run `gh pr create` (through the permission gate).
  In PARITY.md, flip the "PR creation with generated title/body" row from ❌ to ✅ with the
  note "`/pr` gathers branch + commits + diff, agent writes title/body and runs `gh pr create`".
  *Verify:* `grep` confirms JARVIS.md's `Implemented commands:` line and the PARITY
  "PR creation" row both mention `/pr` and the PARITY row is no longer ❌; `/selftest`
  (pytest) green.

---

## Phase 26 — Slash-command autocomplete menu as you type (`/`)

Parity gap: "Slash-command autocomplete menu as you type /" is ❌. The input bar in
`cli.py:_read_input` reads through builtin `input()` + `readline` with `tab: complete`,
which only completes on an explicit Tab press and shows no live menu. Adopt
`prompt_toolkit` as the input backend so typing `/` pops a live dropdown of matching
slash commands, while preserving the boxed status bar, backslash/```` ``` ````
continuation, and history. The prompt_toolkit path is used only when stdin is a real TTY
and the import succeeds; otherwise the current `input()` path is kept unchanged so
one-shot/piped/headless runs and environments without prompt_toolkit still work.

- [x] **26.1 Single source of command names (`jarvis/commands.py`).**
  Lift the hard-coded `commands_list` currently built inside the `/help` branch of
  `handle_command()` into a module-level tuple `_BUILTIN_COMMANDS` (same names, same order)
  and add a helper `def all_command_names() -> list[str]:` returning `list(_BUILTIN_COMMANDS)`
  extended with `f"/{name}"` for each `_discover_custom_commands()` entry. Rewrite the `/help`
  branch to build its printed list from `all_command_names()` (no behavior change). This gives
  the completer and `/help` one shared source.
  *Verify:* a `commands.py` test asserts `all_command_names()` contains `/help`, `/commit`,
  and `/pr`, that every entry starts with `/`, and that there are no duplicates; a second
  asserts `handle_command("/help")` still returns `None` and its captured output mentions
  `/pr`. `/selftest` (pytest) green.

- [x] **26.2 Slash-command completer (`pyproject.toml`, `jarvis/cli.py`).**
  Add `"prompt_toolkit>=3.0"` to `[project].dependencies`. In `cli.py` add a
  `class SlashCommandCompleter(Completer)` (import `Completer`, `Completion` from
  `prompt_toolkit.completion`) whose `get_completions(self, document, complete_event)` reads
  `text = document.text_before_cursor`; if `text` starts with `/` and contains no space, it
  yields a `Completion(name, start_position=-len(text))` for each `name` in
  `all_command_names()` that starts with `text` (case-insensitive); otherwise it yields
  nothing. Keep the completer import-light so `cli.py` still imports if prompt_toolkit is
  absent (guard the top-level import in a `try/except ImportError` that sets a
  `_PROMPT_TOOLKIT` availability flag).
  *Verify:* a `cli.py` test builds `SlashCommandCompleter()` and, using
  `prompt_toolkit.document.Document` and `prompt_toolkit.completion.CompleteEvent`, asserts
  `get_completions(Document("/co", 3), CompleteEvent())` yields texts including `/commit` and
  `/compact` but not `/help`, and `get_completions(Document("hello", 5), CompleteEvent())`
  yields an empty list. `/selftest` (pytest) green.

- [x] **26.3 Route the input bar through prompt_toolkit (`jarvis/cli.py`).**
  Add a lazily-created module-level `PromptSession` (import `PromptSession` from
  `prompt_toolkit`, `InMemoryHistory` from `prompt_toolkit.history`) built with
  `history=InMemoryHistory()`, `completer=SlashCommandCompleter()`, and
  `complete_while_typing=True`. In `_read_input`, when `_PROMPT_TOOLKIT` and
  `sys.stdin.isatty()`, print the top border via `console` as today, read the line with
  `session.prompt("│ > ")` (plain string, styling optional), and print the bottom border in
  the `finally`; on any other case fall back to the existing `input(prompt)` path unchanged.
  Leave `_read_full_input` continuation (`... ` prompt) and the REPL loop's
  `readline.add_history` as-is — the session records its own history on the TTY path and the
  fallback still uses readline.
  *Verify:* a `cli.py` test monkeypatches `sys.stdin.isatty` to return `False` and
  `builtins.input` to return `"hi"`, then asserts `_read_input("~/x · 0k")` returns `"hi"`
  (fallback path intact); the interactive TTY dropdown is exercised manually (note in the PR).
  `/selftest` (pytest) green.

- [x] **26.4 Docs + parity flip (`JARVIS.md`, `PARITY.md`).**
  In JARVIS.md's interactive-UX/input section, document that the input bar uses
  `prompt_toolkit` when stdin is a TTY: typing `/` shows a live completion menu of slash
  commands (builtin + custom) sourced from `commands.all_command_names()`, with a graceful
  `input()`/readline fallback for piped/headless runs or when prompt_toolkit is unavailable.
  In PARITY.md, flip the "Slash-command autocomplete menu as you type /" row from ❌ to ✅
  with the note "prompt_toolkit input bar shows a live `/`-command dropdown on TTY; falls back
  to readline `input()` when piped or prompt_toolkit missing".
  *Verify:* `grep` confirms JARVIS.md mentions `prompt_toolkit` and the PARITY
  "Slash-command autocomplete" row is no longer ❌; `/selftest` (pytest) green.

---

## Phase 27 — Vim editing mode for the input bar

Parity gap: "Vim mode / keybindings" is ❌. It is the topmost genuinely-missing,
self-hostable row: "Plugins / marketplaces" above it is explicitly out of scope, and
"Multiline input (backslash or ``` blocks)" is already implemented in
`cli.py:_read_full_input` (backslash continuation + fenced ```` ``` ```` blocks) despite
its stale ❌. Now that the input bar runs on `prompt_toolkit` (Phase 26), vi-style editing
is a wiring job: `PromptSession` accepts `vi_mode=True` and exposes the resulting
`editing_mode`. Add a persisted `vi_mode` setting, build the session from it, and a `/vim`
toggle command. The readline/`input()` fallback path (no prompt_toolkit or piped stdin)
stays emacs-style and simply ignores the setting.

- [x] **27.1 `vi_mode` setting (`jarvis/settings.py`, `JARVIS.md`).**
  Add `vi_mode: bool = False` to the `Settings` dataclass (with the other scalar bools like
  `show_thinking`), so it participates in `load()`, `load_with_sources()`, and
  `persist_setting()` automatically. Document the key in JARVIS.md's settings list as
  "vi_mode (bool, default false): use vi-style editing keybindings in the prompt_toolkit
  input bar".
  *Verify:* a `settings.py` test asserts `Settings().vi_mode is False`, and that
  `persist_setting("vi_mode", "true", path=tmp)` followed by `Settings.load(path=tmp).vi_mode`
  returns `True`. `/selftest` (pytest) green.

- [x] **27.2 Build the session from the setting (`jarvis/cli.py`).**
  In `_get_prompt_session()`, pass `vi_mode=Settings.load().vi_mode` to the `PromptSession`
  constructor. Add a module-level `def _reset_prompt_session() -> None:` that sets the cached
  `global _prompt_session = None` so the next `_read_input` rebuilds with the current setting
  (needed for the `/vim` toggle to take effect without a restart). Import `Settings` is already
  present in `cli.py`.
  *Verify:* a `cli.py` test (guarded by `_PROMPT_TOOLKIT`) monkeypatches
  `jarvis.cli.Settings.load` to return a `Settings(vi_mode=True)`, calls
  `_reset_prompt_session()` then `_get_prompt_session()`, and asserts the session's
  `editing_mode == prompt_toolkit.enums.EditingMode.VI`; a second run with `vi_mode=False`
  after `_reset_prompt_session()` asserts `EditingMode.EMACS`. `/selftest` (pytest) green.

- [x] **27.3 `/vim` toggle command (`jarvis/commands.py`).**
  Add a `/vim` handler in `handle_command()` modelled on `/theme`: no arg reports the current
  state from `Settings.load().vi_mode` ("Vim mode: on/off"); `on`/`off` (and bare `/vim` as a
  toggle of the current value) call `persist_setting("vi_mode", ...)`, then
  `cli._reset_prompt_session()` (import lazily inside the branch to avoid a cli↔commands import
  cycle), and `print_system(...)` the new state; the handler `return`s. Add `"/vim"` to
  `_BUILTIN_COMMANDS` (after `/theme`) and a `[cyan]/vim [on|off][/cyan]` line to `_HELP_TEXT`.
  *Verify:* a `commands.py` test asserts `handle_command("/vim on")` returns `None` and
  persists `vi_mode=True` (via a monkeypatched/`tmp` settings path), that a no-arg
  `handle_command("/vim")` output mentions "Vim mode", and that `all_command_names()` contains
  `/vim` with no duplicates. `/selftest` (pytest) green.

- [x] **27.4 Docs + parity flip (`JARVIS.md`, `PARITY.md`).**
  In JARVIS.md's interactive-UX/input section and command list, document `/vim [on|off]` and
  that vi-style editing applies on the prompt_toolkit TTY path (fallback `input()`/readline
  stays emacs-style). In PARITY.md, flip the "Vim mode / keybindings" row from ❌ to ✅ with the
  note "prompt_toolkit `vi_mode` on the TTY input bar; `/vim [on|off]` toggle + persisted
  `vi_mode` setting".
  *Verify:* `grep` confirms JARVIS.md mentions `/vim` and the PARITY "Vim mode / keybindings"
  row is no longer ❌; `/selftest` (pytest) green.

---

## Phase 28 — Desktop notification when a long agent turn finishes

Parity gap: "Desktop notifications when a long task finishes" is ❌. With Vim mode (Phase 27)
done, it is the topmost genuinely-missing, self-hostable row: "Plugins / marketplaces" is
explicitly out of scope and "Multiline input" is already implemented in
`cli.py:_read_full_input` (stale ❌). Note `tasks.py` already fires a macOS `osascript`
notification when a *background task* finishes, but the interactive REPL turn (the
`run_agent(...)` call in `cli.py`'s main loop) sends nothing — a user who kicks off a slow
turn and switches away gets no signal when it completes. Add a small cross-platform notifier
(macOS `osascript`, Linux `notify-send`, terminal-bell fallback), a `notify` on/off setting
with a `notify_min_seconds` threshold so quick turns stay silent, and wire it around the
interactive turn so only turns that both finish normally and ran at least the threshold fire.

- [x] **28.1 `notify` + `notify_min_seconds` settings (`jarvis/settings.py`, `JARVIS.md`).**
  Add `notify: bool = True` (next to the other scalar bools like `vi_mode`) and
  `notify_min_seconds: int = 30` (next to the other scalar ints like `tool_timeout_secs`) to the
  `Settings` dataclass, so both participate in `load()`, `load_with_sources()`, and
  `persist_setting()` automatically (int coercion already handled at `persist_setting`). Document
  both keys in JARVIS.md's settings list: "notify (bool, default true): show a desktop
  notification when an interactive agent turn finishes" and "notify_min_seconds (int, default
  30): only notify for turns that ran at least this many seconds".
  *Verify:* a `settings.py` test asserts `Settings().notify is True` and
  `Settings().notify_min_seconds == 30`, and that `persist_setting("notify_min_seconds", "5",
  path=tmp)` followed by `Settings.load(path=tmp).notify_min_seconds` returns `5`. `/selftest`
  (pytest) green.

- [x] **28.2 Cross-platform notifier module (`jarvis/notify.py`, `JARVIS.md`).**
  Add a new module with `def send_notification(title: str, message: str) -> None`. Resolve a
  notifier via `shutil.which`: on `osascript` run
  `["osascript", "-e", f'display notification "{message}" with title "{title}"']`; else on
  `notify-send` run `["notify-send", title, message]`; else write a terminal bell (`"\a"`) to
  `sys.stderr` and flush. Run the chosen command with `subprocess.run(..., timeout=5,
  stdout=DEVNULL, stderr=DEVNULL)` inside a broad `try/except Exception: pass` so a missing or
  hung notifier never surfaces to the REPL (mirrors the "errors never escape" invariant; no
  `formatter.py` output since this is out-of-band). Document the module in JARVIS.md's module
  list / architecture section (1–3 lines).
  *Verify:* a `test_notify.py` monkeypatches `shutil.which` to return `/usr/bin/osascript` and
  `subprocess.run` to a recorder, asserting the argv starts with `["osascript", "-e"]` and
  contains the message; a second test with `which` returning `None` captures `sys.stderr` and
  asserts a `"\a"` was written and no exception raised; a third asserts a raising
  `subprocess.run` is swallowed. `/selftest` (pytest) green.

- [x] **28.3 Notify around the interactive turn (`jarvis/cli.py`).**
  Import `time` and `send_notification`. Wrap the two interactive `run_agent(...)` call sites in
  the main loop — the `/`-command-triggered agent run and the plain-prompt run — so each records
  `start = time.monotonic()` before the call and, only on normal completion (not in the
  `KeyboardInterrupt`/`except Exception` branches), computes `elapsed = time.monotonic() - start`
  and, if `Settings.load().notify` and `elapsed >= Settings.load().notify_min_seconds`, calls
  `send_notification("Jarvis", f"Turn finished in {int(elapsed)}s")`. Factor the shared
  timing+guard into one module-level helper (e.g. `def _notify_turn_done(start: float) -> None:`)
  to avoid duplicating the logic at both sites; the resume-path `run_agent` at startup stays
  unwrapped.
  *Verify:* a `cli.py` test monkeypatches `jarvis.cli.send_notification` to a recorder,
  `Settings.load` to `Settings(notify=True, notify_min_seconds=1)`, and `time.monotonic` to
  return values 2s apart, then calls `_notify_turn_done(start)` and asserts one notification
  fired; a second run with the monotonic delta below the threshold (or `notify=False`) asserts
  none fired. `/selftest` (pytest) green.

- [x] **28.4 Docs + parity flip (`JARVIS.md`, `PARITY.md`).**
  In JARVIS.md's interactive-UX section, document that a desktop notification fires when an
  interactive agent turn finishes and ran at least `notify_min_seconds`, controlled by the
  `notify` setting, degrading to `notify-send` on Linux and a terminal bell when no notifier is
  available. In PARITY.md, flip the "Desktop notifications when a long task finishes" row from ❌
  to ✅ with the note "`notify.py` fires osascript/notify-send (terminal-bell fallback) when an
  interactive turn finishes; gated by `notify` + `notify_min_seconds` settings".
  *Verify:* `grep` confirms JARVIS.md mentions `notify` and the PARITY "Desktop notifications"
  row is no longer ❌; `/selftest` (pytest) green.

---

## Phase 29 — First-class multiline input on the interactive bar

The `\`-continuation and ```-fenced multiline forms already work on the `readline`
fallback path (`cli._read_full_input`, tested), but on an interactive TTY the *first*
line is read through `prompt_toolkit` while each continuation line falls back to a raw
`input("... ")`. On a real TTY that raw `input()` fights `prompt_toolkit` for terminal
state (double-drawn prompts, lost history, a stray slash-command dropdown), so multiline
is only reliable when stdin is piped. This phase routes continuation lines through
`prompt_toolkit` too, then flips the PARITY row.

- [x] **29.1 Completer-free continuation session (`jarvis/cli.py`).**
  Add a module-level `_continuation_session: "PromptSession | None" = None` alongside the
  existing `_prompt_session`, and a `_get_continuation_session() -> "PromptSession"` that
  lazily builds a `PromptSession(history=InMemoryHistory(), completer=None,
  complete_while_typing=False, vi_mode=Settings.load().vi_mode)` — no `SlashCommandCompleter`,
  so typing on a `... ` continuation line never pops the slash dropdown. Extend
  `_reset_prompt_session()` to also set `_continuation_session = None` so `/vim` rebuilds both
  sessions with the current `vi_mode`.
  *Verify:* a `test_cli.py` test calls `cli._get_continuation_session()` twice and asserts the
  same object is returned and its `completer is None`; after `cli._reset_prompt_session()` a
  subsequent call returns a *different* object. `/selftest` (pytest) green.

- [x] **29.2 Route continuation lines through prompt_toolkit (`jarvis/cli.py`).**
  Add a module-level `_read_continuation(prompt: str = "... ") -> str` that, when
  `_PROMPT_TOOLKIT and sys.stdin.isatty()`, reads the line via
  `_get_continuation_session().prompt(prompt)` (letting `prompt_toolkit`'s `EOFError` propagate),
  and otherwise `return input(prompt)`. Replace both `input("... ")` call sites in
  `_read_full_input` (the ```-fenced-block loop and the `\`-continuation loop) with
  `_read_continuation()`, keeping the existing `EOFError` handling unchanged. Because
  `sys.stdin.isatty()` is False under pytest, the non-TTY branch keeps using `input()`, so the
  existing `_read_full_input` tests stay green untouched.
  *Verify:* a `test_cli.py` test monkeypatches `cli.sys.stdin` to an object whose `isatty()`
  returns True and `cli._get_continuation_session` to a stub whose `.prompt` returns `"b"`, then
  monkeypatches `_read_input`→`"a\\"` and asserts `cli._read_full_input("s") == "a\nb"` (the
  continuation came from the session, not `input`); a second test forces the non-TTY branch and
  asserts a monkeypatched `builtins.input` was used. `/selftest` (pytest) green.

- [ ] **29.3 Docs + parity flip (`JARVIS.md`, `PARITY.md`).**
  In JARVIS.md's interactive-UX / `_read_input` paragraph, note that continuation lines
  (`\`-continued and ```-fenced multiline input) are read through a completer-free
  `_get_continuation_session()` on a TTY (raw `input("... ")` fallback off-TTY), so multiline
  editing works on the `prompt_toolkit` bar without a stray slash dropdown. In PARITY.md, flip
  the "Multiline input (backslash or ``` blocks)" row from ❌ to ✅ with the note
  "`\`-continuation + ```-fenced blocks joined by `_read_full_input`; continuation lines routed
  through a completer-free prompt_toolkit session on a TTY".
  *Verify:* `grep` confirms JARVIS.md mentions `_get_continuation_session` and the PARITY
  "Multiline input" row is no longer ❌; `/selftest` (pytest) green.

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
