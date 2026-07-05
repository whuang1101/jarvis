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
- `pipx` for global CLI install from editable local source

## Architecture

```
jarvis/
├── cli.py           Entry point. main(): load Config → build client/tracker/MCP/logger → load
│                    JARVIS.md → connect MCP → run resume.json (if any) → REPL loop (try/finally
│                    calls logger.end on exit). A dim status line (cwd · tokens · plan/auto)
│                    precedes a bare `> ` prompt. Ctrl+C once warns, twice in a row exits
│                    (Ctrl+D still exits immediately).
├── agent.py         Streaming tool-use loop. run_agent() + _stream_turn() (renders live) +
│                    _stream_with_retry() (lazy generator) + _accumulate_tool_calls().
├── client.py        Only file importing openai for requests. stream() (lazy, include_usage),
│                    complete(), current_deployment(), set_deployment().
├── config.py        Frozen Config dataclass. load() searches _ENV_CANDIDATES, validates 4 Azure vars.
├── settings.py      Frozen Settings dataclass (auto_mode, max_tool_iterations, autocompact_tokens,
│                    tool_timeout_secs, theme). load() reads ~/.jarvis/config.toml (tomllib);
│                    missing file = defaults, malformed file = stderr warning + defaults.
├── context.py       ContextManager (history + system prompt), UsageTracker (tokens+cost),
│                    _PRICING table, plan-mode globals, _clean_history, compact().
├── commands.py      handle_command(): all slash commands. Returns None / _EXIT_SENTINEL /
│                    _RUN_AGENT_PREFIX+msg.
├── permissions.py   Auto-mode globals; needs_permission/request_permission; arrow-key Yes/No
│                    selector; unified-diff preview for write_file/edit_file.
├── formatter.py     Shared Rich `console` + Claude-Code-style helpers: print_banner (rounded
│                    welcome panel w/ model+cwd), print_user_header (`> msg`), print_jarvis_header
│                    (`⏺` bullet), render_markdown_block (indented under the bullet),
│                    print_tool_use (`⏺ Read(path)`), print_tool_result (`⎿  summary +N lines`),
│                    make_live_markdown, print_system/print_error/print_command_output.
├── logger.py        SessionLogger — JSONL to ~/.jarvis/logs/YYYY-MM-DD.jsonl (session_start,
│                    user, assistant, tool_call, tool_result[≤500 chars], error, session_end).
├── mcp_manager.py   Daemon-thread asyncio loop. MCPManager.connect() launches a server, lists
│                    tools, parks the session alive; MCPTool wraps each as a BaseTool.
└── tools/
    ├── __init__.py      _REGISTRY (14 built-ins) + get_all_tools/get_tool_by_name/register_tool.
    ├── base.py          BaseTool(ABC): name/description/parameters/execute + to_openai_schema().
    ├── read_file.py     Read a file; truncates at 10,000 chars; files >100KB require
    │                    offset/limit (1-based line slice, output prefixed "N: line").
    ├── write_file.py    Write a file (through permission gate).
    ├── edit_file.py     Replace old_string→new_string; old_string must appear exactly once.
    ├── run_command.py   Run a shell command; intercepts `cd`/`cd <path>` via os.chdir().
    ├── list_dir.py      Directory tree to depth 2, honoring top-level .gitignore.
    ├── search_files.py  grep -rn for a pattern; caps output at 200 lines.
    ├── fetch_url.py     HTTP GET a URL; truncates at 8,000 chars.
    ├── web_search.py    DuckDuckGo search via ddgs.
    ├── web_extract.py   Fetch + extract clean text via trafilatura; truncates at 12,000 chars.
    ├── find_symbol.py   grep for definitions/references of a symbol (word-boundary matched).
    ├── package_info.py  npm / PyPI package metadata lookup.
    └── git_tools.py     git_status, git_diff, git_log (shared _git() helper, 15s timeout).
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
   - `RateLimitError` → retried with fixed delays `(5, 15, 30)` then give up (not exponential).
   - `BadRequestError` matching context-length → compact once and re-stream.
2. Returns `(full_text, collected_tool_calls, finish_reason)`. Tool-call fragments are merged by
   `tc.index` across chunks (`_accumulate_tool_calls`).
3. **Terminate** when `finish_reason == "stop"` OR (`finish_reason != "tool_calls"` AND no tool
   calls collected): append the assistant message and return.
4. Otherwise execute each collected tool call (permission gate → execute → append `role:tool`
   result keyed by `tool_call_id`), then loop.

### Permission gate (`permissions.py`)

- `needs_permission(tool, args)`: `run_command` → True only if it matches `_DESTRUCTIVE_RE`
  (`rm `, `rmdir`, `sudo`, `kill`/`pkill`/`killall`, `git reset --hard`, `git clean -fdx`,
  `DROP TABLE/DATABASE`, `TRUNCATE`, `mkfs`, `fdisk`). **Auto mode never bypasses this.**
  `write_file`/`edit_file` → **always True** (so the diff is shown); in auto mode
  `request_permission` renders the diff then auto-applies, otherwise it prompts.
- `request_permission` prints a unified-diff preview (Rich `Syntax`, "diff") then asks via
  `_arrow_confirm()` — an **arrow-key Yes/No selector** (raw termios; default **No**; Enter
  confirms; y/n jump directly). Returns `None` if approved, else a cancellation string injected
  as the tool result. The edit preview enforces the same uniqueness rule as `edit_file`, so it
  never shows a diff the tool would reject.

### Slash commands (`commands.py`)

`handle_command()` returns `None` (handled in place), `_EXIT_SENTINEL` (`__EXIT__`, exit REPL),
or `_RUN_AGENT_PREFIX` (`__RUN__:`) + message (the REPL strips the prefix and runs it through
`run_agent`). `/retry`, `/fix`, `/go`, `/cancel` use the `_RUN_AGENT_PREFIX` path. Commands are
case-insensitive; the argument keeps original case.

Implemented commands: `/help /history /retry /undo /clear /compact /usage /model /file /run /plan
/go /cancel /restart /auto /fix /copy /save /memory /init /selftest /exit /quit`. Every one is listed in
`_HELP_TEXT` — keep that invariant.

### Plan mode vs auto mode (independent toggles)

- **Plan mode** (`/plan`, state in `context.py`): when on, `_PLAN_MODE_PROMPT` is appended to the
  system prompt instructing the model to research, output a numbered plan, and **stop** — waiting
  for `/go` (execute) or `/cancel` (abort). It does not auto-execute.
- **Auto mode** (`/auto`, state in `permissions.py`): skips the approval prompt for file
  writes/edits (diff still shown, then auto-applied). Destructive shell commands still prompt.

### Cost tracking (`context.py:UsageTracker`)

`record(prompt, completion, deployment)` is called per streaming chunk with `.usage`.
`_lookup_price` lowercases the deployment and matches `_PRICING` keys **longest-first** (so
`gpt-4o-mini` isn't mispriced as `gpt-4o`), falling back to gpt-4o pricing (2.50/10.00 per 1M).
`/usage` shows tokens and estimated USD. `token_estimate()` is rough: total content chars ÷ 4
(ignores tool_calls payloads and the system message).

### MCP integration (`mcp_manager.py`)

A daemon thread runs a persistent asyncio loop. `connect()` launches a server subprocess via
`stdio_client`, initializes the session, lists tools, and parks the coroutine alive; on a 30s
timeout it raises `TimeoutError` (not a bare KeyError). Each tool becomes an `MCPTool(BaseTool)`
registered into the global `_REGISTRY` by `cli._connect_mcp`. Servers connect **at startup only**
(GitHub via `gh auth token` → `GITHUB_PERSONAL_ACCESS_TOKEN`; Azure if `az account show` succeeds;
Brave if `BRAVE_API_KEY` set). If one crashes, restart Jarvis.

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
| `jarvis/context.py` | System prompt, plan-mode prompt, pricing, history cleaning, compaction |
| `jarvis/permissions.py` | What requires approval; diff preview; auto-mode behavior |
| `jarvis/client.py` | Only place that touches the OpenAI SDK for requests |
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

## Common commands

```bash
python3 -m pipx reinstall jarvis     # after any source change (auto-restarts in place)
jarvis                                # run from a dir under this JARVIS.md
pipx list                             # check what's installed
cat ~/.jarvis/logs/$(date +%Y-%m-%d).jsonl | jq .   # view today's session log
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
- `edit_file` needs `old_string` to appear **exactly once** (0 or 2+ → error). The permission
  preview enforces the same rule.
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
