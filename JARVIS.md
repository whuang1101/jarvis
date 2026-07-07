# Jarvis — Project Context

> You (Jarvis) are running *inside* this project. You can read, edit, and improve your own
> source code. This file is your map — keep it accurate. When you change behavior, update the
> matching section here in the same turn (see **Self-improvement workflow → step 5**).

## Improvement backlog

See **`ROADMAP.md`** for the ordered, step-by-step self-improvement plan (do those phases in
order), and **`TODO.md`** for the raw feature/bug backlog. Check it before suggesting new
features — something may already be planned or done. Mark items `[x]` when complete and note the file changed.

## What this is

Jarvis is a self-hosted CLI coding assistant on **Azure OpenAI** (`AzureOpenAI` client). It is a
streaming agentic REPL with tool use, MCP integrations, session logging, a permission/diff gate,
plan mode, auto mode, and persistent memory. Installed globally via `pipx` and invoked as `jarvis`.

## Self-improvement workflow

When told to "work through the TODO list" or "keep going", operate autonomously — do not ask
"should I proceed?" between items. Pick the next uncompleted item, implement it, mark it done,
move on. Stop only when: you've completed 3–5 features (then do the branch/PR workflow), you hit
an error you can't resolve, or the user says stop. (This autonomy is **auto mode**, toggled with
`/auto`. It is independent of **plan mode** — see Key flows.)

The edit loop:

1. **Find** — `search_files` (grep) or `find_symbol` to locate code. Don't bulk-read the repo.
2. **Read** — read only the specific file(s) you need. `read_file` truncates at 10,000 chars.
3. **Edit** — `edit_file` for targeted changes (its `old_string` must be **unique** in the file),
   `write_file` for new files or full rewrites.
4. **Verify** — after every edit, re-read the changed region and check:
   - Every name you used (class, function, variable) is imported or defined in that file
   - Any new import exists in the installed packages or stdlib
   - Indentation/structure is correct
   - If you added a function/class/tool/command, it is wired up where it's called/registered
5. **Update JARVIS.md** — if you added/changed a tool, command, flow, or gotcha, update the
   relevant section here so future sessions stay accurate:
   - New slash command → add to `_HELP_TEXT` **and** the command list below
   - New tool → register in `tools/__init__.py` **and** add to the tool table below
   - New gotcha → add to Known issues
   - Completed idea → remove it from Improvement ideas / check it off in TODO.md
6. **Run the test suite** — `/selftest` (or `python3 -m pytest jarvis/tests -q`). If it fails,
   fix the failure before reinstalling. Add tests when you add behavior.
7. **Set resume state (only if continuing across a restart)** — write `~/.jarvis/resume.json`
   with `write_file`. Schema (all fields read by `cli.py`):
   ```json
   {"message": "Continue the next uncompleted TODO item.", "auto": true, "plan": false}
   ```
   On restart Jarvis reads it, restores `auto`/`plan` mode, deletes the file, and runs `message`
   as the first turn. NOTE: `run_command`'s auto-restart only writes this file when **auto mode
   is on**; a `/restart` or pipx reinstall in non-auto mode re-execs with no resume.
8. **Reinstall and restart** — run `python3 -m pipx reinstall jarvis` via `run_command`. On
   success the tool auto-restarts Jarvis in place (and picks up resume state if written).

## Branching and PR workflow

After every **3–5 completed features**, or when finishing a logical group from TODO.md, create a
branch, open a PR, and merge it:

```bash
git checkout -b feat/<category>-<short-description>
git add -A
git commit -m "<Category>: short summary of features"
git push -u origin feat/<category>-<short-description>
gh pr create --title "<Category>: summary" --body "## What ... ## Why ..."
gh pr merge --squash --delete-branch
git checkout main && git pull
```

**Always squash merge.** Don't wait to be asked — do this as part of the loop.

**Common mistakes to catch in verification:**
- Using `Path` without `from pathlib import Path`, or `Any` without `from typing import Any`
- Referencing a function defined later in the file before its definition
- Adding a tool without registering it in `tools/__init__.py`
- Adding a slash command without adding it to `_HELP_TEXT`
- Duplicating an `if cmd == "/x":` block — handlers all `return`, so a second copy is dead code

## Stack

- Python ≥3.11 (3.13 in practice)
- Azure OpenAI via the `openai` SDK (`AzureOpenAI`); `client.py` is the only file that imports it
  for requests. `agent.py` imports `openai` only for the `BadRequestError`/`RateLimitError` classes.
- **Rich** for all terminal output — `Console`, `Status` spinners, `Syntax`, `Rule`, and crucially
  `rich.live.Live` + `rich.markdown.Markdown` (the streaming render mechanism)
- MCP SDK (`mcp>=1.0`) for GitHub / Azure / Brave Search
- `trafilatura` (web extraction), `ddgs` (DuckDuckGo search)
- `pypdf` (PDF text extraction in `read_file`)
- `pipx` for global CLI install from editable local source

## Architecture

```
jarvis/
├── cli.py           Entry point. main(): load Config → build client/tracker/MCP/logger → load
│                    JARVIS.md → connect MCP → run resume.json (if any) → REPL loop (try/finally
│                    calls logger.end on exit). A dim status line (cwd · tokens · plan/auto)
│                    precedes a bare `> ` prompt. Ctrl+C once warns, twice in a row exits
│                    (Ctrl+D still exits immediately). `-p/--print PROMPT` runs one_shot mode
│                    (_run_one_shot): auto mode on, no banner, MCP skipped unless `--mcp`, exits 0/1.
│                    `--continue` loads the newest sessions.list_sessions() match for cwd into
│                    ContextManager before the REPL starts. `--debug` sets SessionLogger level.
│                    `_read_full_input` joins `\`-continued lines / ```-fenced blocks; input is
│                    run through context.expand_file_mentions (inline `@path` file contents) then
│                    context.build_multimodal_content (image paths → vision parts).
│                    `_read_piped_stdin` returns piped stdin text (None if stdin is a TTY, empty,
│                    or unreadable) for `cat x | jarvis -p` support. `_compose_one_shot_prompt`
│                    joins `-p` prompt + piped text (`"{prompt}\n\n{piped}"` when both present,
│                    whichever exists alone otherwise, None if neither) so a bare `cat x | jarvis`
│                    with no `-p` also runs one-shot mode. `--max-turns N` caps _run_one_shot's
│                    tool-call iterations by passing `max_iterations=N` into run_agent
│                    (default None uses the configured max_tool_iterations). `--model DEPLOYMENT`
│                    overrides `config.deployment` via `dataclasses.replace` in both one-shot mode
│                    and before the interactive REPL's client is built. `--output-format
│                    {text,json,stream-json}` (default `text`) selects headless -p rendering; parsed
│                    into `args.output_format`. `_result_payload(result, is_error, tracker) -> dict`
│                    builds the `{"type":"result",...}` object; `_emit_result(fmt, payload,
│                    init_meta, out)` writes it (plus a `system`/`init` line for `stream-json`) to
│                    `out` — both pure, no I/O beyond the given stream. `_run_one_shot` wires them up:
│                    when `output_format != "text"` it calls `redirect_console(sys.stderr)` first so
│                    human render never touches stdout, captures `run_agent`'s return as `result`
│                    (exceptions become `result=str(e)`, `is_error=True`), then emits the payload to
│                    `sys.stdout` via `_emit_result` before `sys.exit`. `--output-format json` prints a
│                    single `{"type":"result",...}` object; `stream-json` prints newline-delimited
│                    event objects (a `system`/`init` line, then the `result` line) — human render
│                    goes to stderr in both modes so stdout stays machine-readable.
├── agent.py         Streaming tool-use loop. run_agent() + _stream_turn() (renders live) +
│                    _stream_with_retry() (lazy generator) + _accumulate_tool_calls().
├── client.py        Only file importing openai for requests. stream() (lazy, include_usage),
│                    complete(), current_deployment(), set_deployment().
├── config.py        Frozen Config dataclass. load() searches _ENV_CANDIDATES, validates 4 Azure vars.
├── settings.py      Frozen Settings dataclass (auto_mode, max_tool_iterations, autocompact_tokens,
│                    tool_timeout_secs, theme, show_thinking, sandbox, sandbox_allow_network,
│                    statusline, permission_allow/permission_deny glob-pattern tuples). load() reads
│                    ~/.jarvis/config.toml (tomllib), then overlays a
│                    per-project `.jarvis.toml` found by walking cwd + up to 4 parents (same walk
│                    as _find_jarvis_md) — project values win. Missing files = defaults; malformed
│                    file = stderr warning + that file skipped. persist_allow_pattern() appends to
│                    the global config's `[permissions] allow` list on disk (hand-rolled
│                    _dump_toml — tomllib has no writer).
├── status.py        build_default_status(cwd, tokens, plan, auto, danger) — pure function for the
│                    REPL's dim status line (`~`-abbreviated cwd · Nk tokens · PLAN · AUTO · DANGER).
│                    render_status(settings, cwd, tokens, plan, auto, danger) — runs
│                    settings.statusline as a shell command (JSON on stdin) when set, using its
│                    first stdout line; falls back to build_default_status on empty/nonzero/error.
├── context.py       ContextManager (history + system prompt), UsageTracker (tokens+cost),
│                    _PRICING table, plan-mode globals, _clean_history, compact().
│                    expand_file_mentions() inlines `@path` file contents (non-image) into text.
├── commands.py      handle_command(): all slash commands. Returns None / _EXIT_SENTINEL /
│                    _RUN_AGENT_PREFIX+msg.
├── permissions.py   Auto-mode globals; needs_permission (checks config `[permissions]`
│                    allow/deny glob patterns before tool-specific logic) / request_permission;
│                    arrow-key Yes/Always/No selector (Always adds a pattern to the allow list
│                    and persists it); unified-diff preview for write_file/edit_file.
├── formatter.py     Shared Rich `console` + Claude-Code-style helpers: print_banner (rounded
│                    welcome panel w/ model+cwd), print_user_header (`> msg`), print_jarvis_header
│                    (`⏺` bullet), render_markdown_block (indented under the bullet),
│                    print_thinking_header (`✻ Thinking...`), render_thinking_block (dimmed
│                    italic markdown, own live block, closes before the answer's `⏺` prints),
│                    print_tool_use (`⏺ Read(path)`), print_tool_result (`⎿  summary +N lines`),
│                    make_live_markdown, print_system/print_error/print_command_output.
│                    redirect_console(file) sets `console.file` so every print/status/Live call
│                    diverts at once (used to send human render to stderr in headless modes).
├── logger.py        SessionLogger — JSONL to ~/.jarvis/logs/YYYY-MM-DD.jsonl (session_start,
│                    user, assistant, tool_call, tool_result[≤500 chars], error, session_end).
├── sessions.py      SessionStore — dumps full ContextManager history (cwd + first user message
│                    as metadata) to ~/.jarvis/sessions/<timestamp-suffix>.json after every turn;
│                    separate from the JSONL event log, meant for reload/continue.
│                    list_sessions(cwd=None, limit=10) scans that dir, newest session_id first
│                    (timestamp prefix sorts lexicographically), for `--continue`/`/sessions`/`/resume`.
├── mcp_manager.py   Daemon-thread asyncio loop. MCPManager.connect() launches a server, lists
│                    tools, parks the session alive; MCPTool wraps each as a BaseTool.
├── checkpoints.py   In-memory session checkpoints. create(history, label, file_stash) deep-copies
│                    and appends, trimmed to the last 30; get(index) returns a fresh deep copy
│                    (1-based); list_checkpoints() gives label/time/has_files metadata only.
│                    snapshot_files(cwd)/restore_files(sha, cwd) wrap `git stash create`/`apply`
│                    for tracked-file working-tree snapshots (untracked files are not covered).
│                    checkpoint_turn(context, message) snapshots context._history + file_stash
│                    before a new user turn; cli.py calls it ahead of each interactive run_agent.
└── tools/
    ├── __init__.py      _REGISTRY (17 built-ins) + get_all_tools/get_tool_by_name/register_tool.
    ├── base.py          BaseTool(ABC): name/description/parameters/execute + to_openai_schema().
    ├── read_file.py     Read a file; truncates at 10,000 chars; files >100KB require
    │                    offset/limit (1-based line slice, output prefixed "N: line").
    │                    `.ipynb`/`.pdf` extensions are auto-detected and rendered as text:
    │                    `.ipynb` paths are dispatched to documents.render_notebook
    │                    (cell source + compact `# Out:` output text) before the size guard.
    │                    `.pdf` paths are dispatched to documents.extract_pdf_text likewise.
    │                    Image paths (images.is_image_path) are recognised before the size
    │                    guard: attached as visual input (marker string) when `vision` is
    │                    enabled, otherwise a plain note that vision is disabled.
    │                    Refuses to read secret-file patterns (sensitive.py) unless
    │                    dangerously_skip_permissions is set.
    ├── documents.py      render_notebook(path) — renders a Jupyter notebook's cells as
    │                    `# %% [markdown]`/`# %% [code]` blocks with a `# Out:` section.
    │                    extract_pdf_text(path) — concatenates pypdf page text with
    │                    `--- page N ---` separators; returns "Error: ..." on bad PDFs.
    ├── write_file.py    Write a file (through permission gate).
    ├── edit_file.py     Replace old_string→new_string; old_string must appear exactly once.
    ├── run_command.py   Run a shell command via Popen, streaming stdout/stderr lines live to
    │                    the console as they arrive (result is still the captured, truncated
    │                    text); intercepts `cd`/`cd <path>` via os.chdir(). `background=true`
    │                    instead launches it detached via `tasks.start_background_task()` and
    │                    returns a task id right away. `_build_sandbox_argv(command, cwd,
    │                    allow_network)` builds a `bwrap` argv (read-only `/` bind, read-write
    │                    `cwd` bind, `--unshare-net` unless network allowed); returns `[]` if
    │                    `bwrap` isn't on PATH. When `is_sandbox()` is true, `execute` runs that
    │                    argv with `shell=False`, or returns an `Error:` string if `bwrap` is
    │                    missing instead of falling back to unsandboxed execution.
    ├── task_output.py   Reads a background task's status/log by id (tasks.py: subshell wrapped
    │                    with `>> <id>.log`, exit code written to `<id>.status`, best-effort
    │                    `osascript` notification on completion).
    ├── list_dir.py      Directory tree to depth 2, honoring top-level .gitignore.
    ├── search_files.py  grep -rn for a pattern; caps output at 200 lines; excludes and
    │                    post-filters secret-file patterns (sensitive.py) unless
    │                    dangerously_skip_permissions is set.
    ├── fetch_url.py     HTTP GET a URL; truncates at 8,000 chars.
    ├── web_search.py    DuckDuckGo search via ddgs.
    ├── web_extract.py   Fetch + extract clean text via trafilatura; truncates at 12,000 chars.
    ├── find_symbol.py   grep for definitions/references of a symbol (word-boundary matched).
    ├── glob_files.py    root.glob(pattern), files only, hidden paths skipped, newest-first,
    │                    capped at 200.
    ├── sensitive.py      is_sensitive_path(path)/sensitive_read_error(path) — glob-matches
    │                    basenames against secret-file patterns (.env, *.pem, id_rsa, …);
    │                    wired into read_file.py and search_files.py.
    ├── package_info.py  npm / PyPI package metadata lookup.
    ├── skill.py         Loads a named skill's full body on demand via skills.load_skill();
    │                    returns an `Error:` string if no skill matches.
    ├── git_tools.py     git_status, git_diff, git_log (shared _git() helper, 15s timeout).
    ├── todo_write.py    Replaces the visible task list wholesale (content + pending/in_progress/
    │                    completed), writes it into jarvis/todos.py's module-level store (a
    │                    session-lifetime list, recallable any time via `/todos`), and
    │                    re-renders it via formatter.print_todo_list.
    └── spawn_agent.py   Runs a fresh run_agent() in its own ContextManager (same client/tracker),
                         restricted to a read-only tool subset, capped at 25 iterations, and
                         returns only the final text. allow_subagents=False on the nested call
                         strips spawn_agent from its own tool set so it can't recurse.
```

## Key flows

### Streaming agent loop (`agent.py`)

`run_agent()` auto-compacts if `token_estimate() > 25_000` (**before** appending the new user
message so it isn't folded into the summary), then loops up to `_MAX_TOOL_ITERATIONS = 40`.
If the cap is hit, it injects a user message asking for a progress summary and streams one
final response. Each tool result is capped by `truncate_tool_result()` (8K chars → first 6K +
last 1.5K) and each `tool.execute()` runs through `execute_with_timeout()` (60s, worker
thread → `"Error: tool timed out"` instead of a crash). Ctrl+C mid-stream keeps the partial
text (marked `[interrupted by user]`) and returns to the prompt. Each iteration:

1. `_stream_turn(client, context, tracker)` streams one model response **live**: chunks arrive
   lazily from `_stream_with_retry` (a generator — it does **not** buffer with `list()`), and on
   the first content delta it prints the Jarvis header and renders an incrementally-updated
   `rich.live.Live` Markdown widget. A `Thinking…` spinner runs until the first chunk.
   Reasoning deltas (`delta.reasoning_content` / `delta.reasoning`) accumulate into a separate
   `state["thinking"]` buffer, gated on `settings.show_thinking`, and render in their own dimmed
   italic live block (`print_thinking_header` + `render_thinking_block`) that closes as soon as
   real content arrives — reasoning never enters `state["text"]`/`full_text`.
   - `RateLimitError` → retried with fixed delays `(5, 15, 30)` then give up (not exponential).
   - `BadRequestError` matching context-length → compact once and re-stream.
2. Returns `(full_text, collected_tool_calls, finish_reason)`. Tool-call fragments are merged by
   `tc.index` across chunks (`_accumulate_tool_calls`).
3. **Terminate** when `finish_reason == "stop"` OR (`finish_reason != "tool_calls"` AND no tool
   calls collected): append the assistant message and return.
4. Otherwise execute each collected tool call (permission gate → pre-tool hooks → execute →
   post-tool hooks → append `role:tool` result keyed by `tool_call_id`), then loop.

### Pre/post tool hooks (`agent.py:run_pre_tool_hooks`/`run_post_tool_hooks`)

Configured via `[hooks] pre_tool`/`post_tool` (arrays of `{match, run}` tables; `match` is an
`fnmatch` glob against the tool name). Each matching hook runs `run` via `subprocess.run(shell=True)`
with `{"tool": tool_name, "args": args}` as JSON on stdin, 10s timeout. A pre-hook exiting with
code 2 blocks the tool call — its stderr becomes the tool result. Post-hooks run after a
successful `execute()` for side effects only; their output/exit code is ignored.

### Permission gate (`permissions.py`)

- `needs_permission(tool, args, settings=None)`: first checks `settings.permission_deny` glob
  patterns (`tool_name(glob)`, e.g. `run_command(git push*)`) → True if matched (always gated);
  then `settings.permission_allow` → False if matched (never gated), deny wins on overlap. Falls
  back to the built-in logic: `run_command` → True only if it matches `_DESTRUCTIVE_RE`
  (`rm `, `rmdir`, `sudo`, `kill`/`pkill`/`killall`, `git reset --hard`, `git clean -fdx`,
  `DROP TABLE/DATABASE`, `TRUNCATE`, `mkfs`, `fdisk`). **Auto mode never bypasses this.**
  `write_file`/`edit_file` → **always True** (so the diff is shown); in auto mode
  `request_permission` renders the diff then auto-applies, otherwise it prompts.
- `request_permission` prints a unified-diff preview (Rich `Syntax`, "diff") then asks via
  `_arrow_confirm()` — an **arrow-key Yes/Always/No selector** (raw termios; default **No**;
  left/right or up/down cycle; Enter confirms; y/a/n jump directly). Returns `None` if approved,
  else a cancellation string injected as the tool result. Choosing **Always** derives a glob
  pattern via `_suggest_pattern` (`run_command` scopes to the invoked program, e.g.
  `run_command(git *)`; file ops scope to the whole tool, e.g. `write_file(*)`), adds it to the
  in-memory `_settings.permission_allow` for the rest of the process, and persists it to
  `~/.jarvis/config.toml` via `settings.persist_allow_pattern` (hand-rolled TOML writer —
  `tomllib` is read-only — that preserves the rest of the file). The edit preview enforces the
  same uniqueness rule as `edit_file`, so it never shows a diff the tool would reject.

### Slash commands (`commands.py`)

`handle_command()` returns `None` (handled in place), `_EXIT_SENTINEL` (`__EXIT__`, exit REPL),
or `_RUN_AGENT_PREFIX` (`__RUN__:`) + message (the REPL strips the prefix and runs it through
`run_agent`). `/retry`, `/fix`, `/go`, `/cancel` use the `_RUN_AGENT_PREFIX` path. Commands are
case-insensitive; the argument keeps original case.

Implemented commands: `/help /history /retry /undo /clear /compact /usage /model /theme /statusline /diff /pin
/config /file /run /plan /go /cancel /restart /auto /sandbox /fix /copy /save /sessions /resume /rewind /mcp
/memory /todos /skills /init /selftest /commit /review /pr /exit /quit`. Every one is listed in `_HELP_TEXT` — keep
that invariant. `/sandbox [on|off|status]` shows or toggles `permissions.is_sandbox()`/`set_sandbox()`
(no arg or `status` just prints current state).
`/todos` prints the maintained todo list via `formatter.print_todo_list`; `/todos clear` clears it.
`ContextManager.system_message` also appends a `## Current Todos` section (one `- [ ]`/`- [x]` line
per item, `(in progress)` suffix for in-progress) whenever `todos.get_todos()` is non-empty, so the
agent re-sees its own checklist every turn.
`ContextManager.system_message` also appends a `## Skills` section (one `- <name>: <description>`
line per skill from `discover_skills()`, plus an instruction to call the `skill` tool to load one)
whenever any skills are discovered; omitted entirely when there are none.
`/theme` sets the Rich code-block Pygments style (persisted via `persist_setting`); `/statusline [cmd]`
shows/sets/clears (`off`) the `statusline` setting the same way. `/diff` shows
`git diff HEAD`; `/pin <text>` adds a note into `ContextManager._pinned`, which is rendered into the
system prompt and survives `clear()`/`compact()`. `/selftest` runs pytest **and** mypy. `/commit` stages
with `git add -A`, then hands `git diff --staged` to the agent to write the message and run `git
commit` itself (so the commit goes through the normal tool permission gate). `/review [pr#]` fetches
`git diff main` (or `gh pr diff <pr#>`) and hands it to the agent with a review prompt. Both return
via `_RUN_AGENT_PREFIX`. `_pr_context()` gathers the current branch, `git log main..HEAD` commit
subjects, and `git diff main...HEAD` into a single context string (or an error if on `main` or the
diff is empty). `/pr` calls `_pr_context()` and hands the result to the agent with a prompt to
write a title/body and run `gh pr create --title "<title>" --body "<body>"` itself (same
tool-permission-gate pattern as `/commit`).
Any other `/name` falls back to a
custom command lookup. Inline `@path` mentions work in any normal message too — not just
`/file` — attaching that file's contents at that point in the prompt, so `@path` can be
stacked mid-sentence with surrounding text; image `@mentions` still route to vision instead.
`_load_custom_command` checks `~/.jarvis/commands/<name>.md` then
`.jarvis/commands/<name>.md` (project, global wins on conflict), substitutes `$ARGUMENTS` in the file
content with the command's args, and returns it via `_RUN_AGENT_PREFIX`. `_discover_custom_commands`
lists both dirs' `*.md` stems; `all_command_names()` combines the module-level `_BUILTIN_COMMANDS`
tuple with `f"/{name}"` for each discovered custom command, and is the single source the plain
`/help` command list (and the completer) build from. `cli.py:SlashCommandCompleter` (a
`prompt_toolkit` `Completer`, guarded behind a `_PROMPT_TOOLKIT` import flag so `cli.py` still
loads without the dependency) completes a bare `/prefix` against `all_command_names()`; it is
not yet wired into the input loop (that's `readline` today). `/config` (no args) prints
effective settings from `Settings.load_with_sources()` (default/global/project); `/config <key>
<value>` writes a scalar key to the global TOML via `settings.persist_setting`. `/sessions` lists
`sessions.list_sessions(limit=10)`; `/resume <n>` loads that entry via `SessionStore.load` into
`context.load_history()` and updates the REPL's live `SessionStore` in place so later autosaves
keep writing to the resumed session file. `/rewind` with no arg lists `checkpoints.list_checkpoints()`
entries (1-based, ` [files]` suffix for `has_files`); `/rewind <n>` restores checkpoint `n`'s history
via `context.load_history()` and, if it carries a `file_stash`, applies it via `checkpoints.restore_files()`;
`/rewind clear` calls `checkpoints.clear()`. `/memory add <text>` appends to `~/.jarvis/memory.md`
via the module-level `append_memory(text)` helper (creates the parent dir, never raises). The REPL
loop also treats a bare `#text` line (checked before the `/` dispatch) as a shortcut for the same
`append_memory` call, printing the result without sending the text to the agent; `#` with no text
is a no-op.

### Plan mode vs auto mode (independent toggles)

- **Plan mode** (`/plan`, state in `context.py`): when on, `_PLAN_MODE_PROMPT` is appended to the
  system prompt instructing the model to research, output a numbered plan, and **stop** — waiting
  for `/go` (execute) or `/cancel` (abort). It does not auto-execute.
- **Auto mode** (`/auto`, state in `permissions.py`): skips the approval prompt for file
  writes/edits (diff still shown, then auto-applied). Destructive shell commands still prompt.

### Cost tracking (`context.py:UsageTracker`)

`record(prompt, completion, deployment, cached=0)` is called per streaming chunk with `.usage`, reading
`cached` off `usage.prompt_tokens_details.cached_tokens` (defaults to 0 if absent); `client.complete()`
surfaces the same value via `CompleteResult.cached_tokens` for the compaction path.
`_lookup_price` lowercases the deployment and matches `_PRICING` keys **longest-first** (so
`gpt-4o-mini` isn't mispriced as `gpt-4o`), falling back to gpt-4o pricing (2.50/10.00 per 1M).
`cached` (a subset of `prompt`) tracks cached-prompt tokens in `cached_tokens` and bills them at
half the input rate. `/usage` shows tokens, estimated USD, and a "Cached (of prompt)" line with
hit-rate %; the headless JSON result's `usage` dict includes `cached_input_tokens`.
`token_estimate()` is rough: total content chars ÷ 4 (ignores tool_calls payloads and the system message).

### MCP integration (`mcp_manager.py`)

A daemon thread runs a persistent asyncio loop. `connect()` launches a server subprocess via
`stdio_client`, initializes the session, lists tools, and parks the coroutine alive; on a 30s
timeout it raises `TimeoutError` (not a bare KeyError). Each tool becomes an `MCPTool(BaseTool)`
registered into the global `_REGISTRY` by `cli._connect_mcp`. Servers connect **at startup only**
(GitHub via `gh auth token` → `GITHUB_PERSONAL_ACCESS_TOKEN`; Azure if `az account show` succeeds;
Brave if `BRAVE_API_KEY` set). `connect()` also records spawn params in `self._server_params[name]`;
`reconnect(name)` disconnects and re-`connect()`s a crashed server from those saved params,
returning `False` if the server was never connected or the respawn raises. `_call_tool` retries
a failed call once via `reconnect()` when `Settings.load().mcp_auto_reconnect` is true (default),
returning an `"Error: ..."` string if reconnect is disabled or fails.
`list_servers()`/`disconnect(name)` give introspection and teardown; `set_active_manager`/
`get_active_manager` expose the running `MCPManager` module-wide (set in `cli.py` at startup).
`/mcp` (no arg or `list`) prints `list_servers()` as `name — tool_count tools`; `/mcp add <name>
<command> [args...]` calls `mgr.connect()` and `register_tool`s the results; `/mcp remove <name>`
calls `mgr.disconnect()` and `unregister_tool`s the returned names — all a no-op with an error line
if no manager is active.
After the hardcoded servers, `_init_mcp` also connects every entry from
`mcp_config.load_mcp_servers()`, which merges a global `~/.jarvis/mcp.json` with a project
`.mcp.json` (walked up from `cwd`, 5 levels, project wins), each shaped
`{"mcpServers": {name: {command, args, env}}}`.

### JARVIS.md loading (`cli.py:_find_jarvis_md`)

Checks `cwd` and up to 4 parent directories (5 candidates total), stopping at the filesystem
root. First hit is injected into the system prompt as project context. This file is that context.

## Conventions

- All terminal output goes through `formatter.py` helpers and the shared `console` — never `print()`.
- Tools return plain **strings** (not JSON, not Rich markup). Tool errors return `"Error: ..."`
  strings rather than raising — `run_agent` also wraps `execute()` to catch stragglers.
- New tools subclass `BaseTool` and are added to `_REGISTRY` in `tools/__init__.py`.
- New slash commands go in `commands.py:handle_command()` with a matching `_HELP_TEXT` entry. Each
  handler must `return` (None/sentinel/run-prefix); don't fall through.
- Plan-mode and auto-mode state are **module-level globals**, not per-instance.

## Key files to know

| File | Why it matters |
|---|---|
| `jarvis/agent.py` | Central loop + live streaming — start here for model-interaction changes |
| `jarvis/tools/__init__.py` | Register new tools here |
| `jarvis/commands.py` | Add new slash commands here (+ `_HELP_TEXT`) |
| `jarvis/context.py` | System prompt (search-before-read, verify-after-edit, ask-before-destructive habits), plan-mode prompt, pricing, history cleaning, compaction |
| `jarvis/permissions.py` | What requires approval; diff preview; auto-mode behavior |
| `jarvis/client.py` | Only place that touches the OpenAI SDK for requests |
| `jarvis/images.py` | Pure helpers to detect image files and encode them as `image_url` content parts for vision input |
| `jarvis/skills.py` | Discovers/parses auto-triggered skills from `~/.jarvis/skills/` and `./.jarvis/skills/` (`<name>.md` or `<name>/SKILL.md`, project overrides global) |
| `pyproject.toml` | Dependencies and the `jarvis` entry point |

## Environment variables (in `.env`, gitignored)

```
AZURE_OPENAI_ENDPOINT=https://....openai.azure.com/
AZURE_OPENAI_API_KEY=...
AZURE_OPENAI_DEPLOYMENT=gpt-4o
AZURE_OPENAI_API_VERSION=2024-08-01-preview
BRAVE_API_KEY=...           # optional — enables Brave Search MCP
```

`.env` search order (first existing wins, `override=False`): `cwd/.env` → `~/.jarvis.env` →
`~/jarvis/.env` → package-root `.env`. All four `AZURE_OPENAI_*` vars are required or `load()` raises.

## Runtime settings (`~/.jarvis/config.toml` + per-project `.jarvis.toml`, both optional)

```toml
auto_mode = false
dangerously_skip_permissions = false
max_tool_iterations = 40
autocompact_tokens = 25000
tool_timeout_secs = 60
theme = "monokai"
show_thinking = true
vision = true
mcp_auto_reconnect = true
sandbox = false
sandbox_allow_network = false
statusline = ""

[permissions]
allow = ["write_file(*)"]          # glob patterns matched against "tool_name(args)"
deny = ["run_command(git push*)"]

[hooks]
pre_tool = [{match = "write_file", run = "./block_writes.sh"}]   # match is a glob on tool name
post_tool = [{match = "*", run = "./notify.sh"}]
```

`Settings.load()` reads the global file first, then walks up from cwd (through up to 4 parents,
same walk as `_find_jarvis_md`) looking for a project `.jarvis.toml` and overlays any keys it
sets — project values win over global values, both win over the dataclass defaults above. Missing
files fall back silently; a malformed file prints a stderr warning and that file's values are
skipped (the other file/defaults still apply). Unknown keys are ignored. Currently informs
`agent.py`'s iteration cap / tool timeout / autocompact threshold and `permissions.py`'s
`auto_mode`, `dangerously_skip_permissions`, and `sandbox`/`sandbox_allow_network` defaults
(mirrored into `permissions._sandbox` via `is_sandbox()`/`set_sandbox()`); nothing consumes
`theme` yet.
`sandbox` (bool, default false) routes `run_command` through a `bwrap` sandbox (read-only `/`,
writable cwd, network off unless `sandbox_allow_network` is true); requires `bwrap` on PATH
(Linux only) and is deny-by-default — if `bwrap` is missing while sandboxing is on, `execute`
returns an `Error:` instead of falling back to unsandboxed execution. Toggle at runtime with
`/sandbox [on|off|status]`.
`show_thinking` (default `true`) is read once by `JarvisClient.__init__` into
`self._show_thinking` (unused there); `agent.py._stream_turn` reads its own module-level
`_settings.show_thinking` to gate whether reasoning deltas are rendered (7.2).
`vision` (bool, default true) — attach image files read with `read_file` to the conversation as
visual input; set false to disable.
`mcp_auto_reconnect` (bool, default true) — gates whether `mcp_manager._call_tool` retries a
failed call once via `reconnect()`; false skips the retry and returns the error immediately.
`statusline` (str, default `""`) — a shell command; when set, `status.render_status` runs it
before each prompt read (JSON of cwd/tokens/plan/auto/danger on stdin) and uses its first stdout
line as the input-bar top-border status; an empty/nonzero/timing-out (`tool_timeout_secs`) result
or any exception falls back to the built-in `build_default_status`. Set/view/clear with
`/statusline [cmd]` (`/statusline off` clears it, no arg shows the current value).

`[permissions] allow`/`deny` are glob-style pattern lists (`fnmatch`) checked in
`permissions.py:needs_permission` before the tool-specific logic: a `deny` match forces the
permission gate even for tools that wouldn't normally trigger it (e.g. gating a specific
`run_command` pattern); an `allow` match skips the gate even for tools that always would (e.g.
`write_file(*)` to stop prompting for every file write). Deny is checked first, so it wins over
an overlapping allow pattern. Patterns render as `run_command(<command>)`,
`write_file(<path>)`/`edit_file(<path>)`, or `tool_name(<args joined by ", ">)` for anything else.

The `allow` list also grows interactively: at any permission prompt, picking **Always**
(the middle option of the Yes/Always/No selector) approves that call, adds a pattern for it
to the in-memory settings, and writes it into `[permissions] allow` in `~/.jarvis/config.toml`
via `settings.persist_allow_pattern` — so the same command/tool family is auto-approved for
the rest of this run and every run after.

## Skills (auto-triggered markdown capabilities)

Skills live in two directories — global `~/.jarvis/skills/` and project `./.jarvis/skills/`
(project overrides global on name conflict) — as either a flat `<name>.md` file or a
`<name>/SKILL.md` file, each with an optional leading `---`-fenced frontmatter block carrying
`name:`/`description:` keys (`jarvis/skills.py:discover_skills`/`_parse`; name falls back to the
file/dir stem if omitted). `ContextManager.system_message` injects a `## Skills` catalog into the
system prompt — one `- <name>: <description>` line per discovered skill plus an instruction to
load one — omitted entirely when none are found. The model loads a skill's full body on demand via
the `skill` tool (`jarvis/tools/skill.py`, wraps `skills.load_skill`), and a human can list them
with the `/skills` command.

## Common commands

```bash
python3 -m pipx reinstall jarvis     # after any source change (auto-restarts in place)
jarvis                                # run from a dir under this JARVIS.md
pipx list                             # check what's installed
cat ~/.jarvis/logs/$(date +%Y-%m-%d).jsonl | jq .   # view today's session log
cat err.log | jarvis -p "fix this"   # piped text appended below the -p prompt
git diff | jarvis                     # bare pipe: piped text is the whole prompt (TTY never read)
jarvis -p "..." --max-turns 3         # cap tool-call iterations for this one-shot run
jarvis --model gpt-4o-mini            # override the Azure deployment (interactive or -p)
```

## How to add a new tool

1. Create `jarvis/tools/my_tool.py` subclassing `BaseTool` (`name`, `description`, `parameters`,
   `execute(self, args) -> str`). Catch failures and return `"Error: ..."`.
2. Import it and add an instance to `_REGISTRY` in `jarvis/tools/__init__.py`.
3. Add a row to the tool table above. Reinstall.

## How to add a new slash command

1. Add an `if cmd == "/x":` block in `commands.py:handle_command()` that returns
   None / `_EXIT_SENTINEL` / `f"{_RUN_AGENT_PREFIX}message"`.
2. Add an entry to `_HELP_TEXT` and to the command list under Key flows. Reinstall.

## Known issues / gotchas

- `cd` in `run_command` persists via `os.chdir()` (bare `cd` → home; `cd <path>` → that dir; not
  triggered by lookalikes like `cdiff`). The prompt's cwd updates on the next REPL iteration.
- MCP servers connect at startup only — if one crashes, restart Jarvis.
- `stream_options={"include_usage": True}` is required for real token counts from Azure.
- `edit_file` needs `old_string` to appear **exactly once** (0 or 2+ → error, with the offending
  line numbers listed), unless `replace_all=true` is passed. The permission preview enforces the
  same rule.
- `token_estimate()` is a chars÷4 approximation and ignores tool_call payloads + system prompt.
- Cost figures use the hardcoded `_PRICING` table; real Azure pricing may differ.
- `_history` holds raw message dicts (user/assistant/tool/tool_calls), so `/usage`'s
  "N messages" and `/history` include tool-result and tool-call entries, not just turns.
- The `build/` directory is a stale copy — the live source is `jarvis/`. Ignore `build/` and `.venv/`.

## Improvement ideas

- Multi-file context (auto-load all files matching a glob for `/file`)
- Interrupt mid-stream with Ctrl+C to start a new message (currently cancels the turn)
- Proactive auto-compact at a token threshold (today: warn at ~20K; compact only reactively on a
  context-length API error)
- Test suite — none yet; `jarvis/tests/` with unit tests for `permissions.py`, `context.py`, and
  each tool's `execute()` would be the path
- Syntax-highlighted code blocks during streaming (currently plain Markdown via Live)
- `/pin` a message that survives `/compact` and `/clear`
