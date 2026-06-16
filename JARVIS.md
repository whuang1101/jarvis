# Jarvis — Project Context

## Improvement backlog

See **`TODO.md`** in this directory for the full prioritized list of features to build and bugs to fix. Check it before suggesting new features — something may already be planned or completed. Mark items `[x]` when done.

## What this is

Jarvis is a self-hosted CLI coding assistant built on Azure OpenAI (gpt-4o). It is a streaming agentic REPL with tool use, MCP server integrations, session logging, and a permission/diff system. The CLI is installed globally via `pipx` and invoked with `jarvis`.

You are running *inside* this project right now. You can read, edit, and improve your own source code.

## Self-improvement workflow

When asked to add a feature, fix a bug, or improve yourself, follow this loop:

1. **Find** — use `search_files` or `find_symbol` to locate the relevant code. Don't bulk-read the whole repo.
2. **Read** — read only the specific file(s) you need.
3. **Edit** — use `edit_file` for targeted changes, `write_file` only for new files or full rewrites.
4. **Verify** — after every edit, re-read the changed file and check:
   - All names you used (classes, functions, variables) are imported or defined in that file
   - Any new import you added actually exists in the installed packages or stdlib
   - The indentation and structure look correct
   - If you added a function/class, check that it's wired up where it needs to be called
5. **Update JARVIS.md** — if the feature adds a new tool, command, flow, or gotcha, update the relevant section of this file so future sessions have accurate context. Specifically:
   - New slash command → add to the commands table and `_HELP_TEXT` note
   - New tool → add to the architecture file list
   - New gotcha or known issue → add to the Known issues section
   - New improvement idea completed → remove it from Improvement ideas
6. **Reinstall** — use the `run_command` tool to run `python3 -m pipx reinstall jarvis`. This updates the installed binary from your edited source files.
7. **Tell the user to restart** — after reinstalling, tell the user to type `/restart` at the prompt. Do NOT try to run `/restart` or `jarvis --restart` as a shell command — `/restart` is a REPL slash command that only works when typed at the prompt. Running it via `run_command` will fail.

**Common mistakes to catch in step 4:**
- Using `Path` without `from pathlib import Path`
- Using `Any` without `from typing import Any`
- Referencing a function defined later in the file before its definition
- Adding a new tool without registering it in `tools/__init__.py`
- Adding a new slash command without adding it to `_HELP_TEXT`

The user does not need to explain the architecture — you have full context from this file. When in doubt about where something lives, check the architecture map below before reading files.

## Stack

- Python 3.11+ (3.13 in practice)
- Azure OpenAI (`openai` SDK, `AzureOpenAI` client, gpt-4o deployment)
- Rich (all terminal output — Console, Status spinners, Syntax, Rule)
- MCP SDK (`mcp>=1.0`) for GitHub / Azure / Brave Search integrations
- trafilatura (web content extraction), ddgs (DuckDuckGo search)
- pipx for global CLI install from editable local source

## Architecture

```
jarvis/
├── cli.py           Entry point. REPL loop, MCP init, JARVIS.md loading.
├── agent.py         Streaming tool-use loop. Drives all model interactions.
├── client.py        Only file that imports openai. stream() / complete() / set_deployment().
├── config.py        Loads .env from candidate paths. Validates 4 Azure env vars.
├── context.py       ContextManager (message history), UsageTracker (tokens + cost), pricing table.
├── commands.py      Slash command handlers (/help /usage /model /fix /file /run /clear /compact /init).
├── permissions.py   Diff preview + y/N gate for write_file, edit_file, and destructive shell commands.
├── formatter.py     Rich helpers: print_banner, print_streaming_token, print_system, print_error.
├── logger.py        SessionLogger — JSONL logs to ~/.jarvis/logs/YYYY-MM-DD.jsonl.
├── mcp_manager.py   Async MCP client via background daemon thread + asyncio event loop.
└── tools/
    ├── __init__.py      Tool registry (_REGISTRY list). register_tool() for MCP tools.
    ├── base.py          BaseTool abstract class (name, description, parameters, execute, to_openai_schema).
    ├── read_file.py     Read any file.
    ├── write_file.py    Write file (goes through permission gate).
    ├── edit_file.py     Targeted old_string → new_string replacement (goes through permission gate).
    ├── run_command.py   Run shell command. Intercepts `cd` and calls os.chdir().
    ├── list_dir.py      List directory contents.
    ├── search_files.py  Grep/ripgrep for patterns.
    ├── fetch_url.py     HTTP GET a URL.
    ├── web_search.py    DuckDuckGo search via ddgs.
    ├── web_extract.py   Fetch URL and extract clean text via trafilatura.
    ├── find_symbol.py   Find function/class definitions in source files.
    ├── package_info.py  Look up package metadata.
    └── git_tools.py     git_status, git_diff (staged/file/ref), git_log.
```

## Key flows

### Streaming agent loop (`agent.py:run_agent`)

1. Append user message to `ContextManager`
2. Call `client.stream(context.messages(), tools=tool_schemas)` — Azure streams chunks
3. Accumulate text tokens (print immediately via `print_streaming_token`) and tool call fragments
4. On `finish_reason == "stop"` → append assistant message, return
5. On `finish_reason == "tool_calls"` → for each tool call:
   - Run `needs_permission()` — if yes, show diff/warning and prompt y/N
   - Execute tool, append `role: tool` result to context
6. Loop up to `_MAX_TOOL_ITERATIONS = 10`

### Permission gate (`permissions.py`)

- `needs_permission()` returns True for `write_file`, `edit_file`, and `run_command` matching `_DESTRUCTIVE_RE`
- `request_permission()` shows a unified diff (for file ops) or warning (for commands) and prompts `Apply? [y/N]`
- Returns `None` if approved, or a cancellation string to inject as the tool result if denied

### Slash commands (`commands.py`)

`handle_command()` returns:
- `None` → nothing to do
- `_EXIT_SENTINEL` → exit REPL
- `_RUN_AGENT_PREFIX + message` → `cli.py` extracts the message and calls `run_agent()`

### Cost tracking (`context.py:UsageTracker`)

- `tracker.record(prompt, completion, deployment)` called per streaming response chunk that has `.usage`
- `_lookup_price(deployment)` matches deployment name against `_PRICING` dict (substring match, case-insensitive)
- `/usage` shows total tokens and `$0.0000` estimated cost

### MCP integration (`mcp_manager.py`)

- Daemon thread runs a persistent asyncio event loop
- `mcp.connect()` launches an MCP server subprocess, initializes the session, lists tools, then parks with `await asyncio.Event().wait()` to keep it alive
- Each MCP tool becomes an `MCPTool(BaseTool)` registered into the global `_REGISTRY`
- GitHub: uses `gh auth token` CLI (falls back to `GITHUB_PERSONAL_ACCESS_TOKEN` env)
- Azure: uses `az login` / DefaultAzureCredential (checks `az account show` first)
- Brave Search: needs `BRAVE_API_KEY` in `.env`

### JARVIS.md loading (`cli.py:_find_jarvis_md`)

Walks up 5 directory levels from `cwd` looking for `JARVIS.md`. When found, its content is injected into the system prompt via `ContextManager(project_context=...)`. This file is that context.

## Conventions

- All terminal output goes through `formatter.py` helpers — never `print()` directly
- Tools return plain strings (not JSON, not Rich markup)
- Tool errors should return `"Error: ..."` strings, not raise exceptions (agent handles them gracefully)
- New tools must subclass `BaseTool` and be added to `_REGISTRY` in `tools/__init__.py`
- New slash commands go in `commands.py:handle_command()` with a matching entry in `_HELP_TEXT`
- Streaming token display uses `print_streaming_token()` which writes directly to stdout without a newline
- `console.print()` (bare) adds the newline after streaming finishes

## Key files to know

| File | Why it matters |
|---|---|
| `jarvis/agent.py` | Central loop — start here when changing model interaction behavior |
| `jarvis/tools/__init__.py` | Add new tools here |
| `jarvis/commands.py` | Add new slash commands here |
| `jarvis/context.py` | Change system prompt, pricing, or token tracking here |
| `jarvis/permissions.py` | Change what requires approval or how diffs are shown |
| `jarvis/client.py` | Only place that touches the OpenAI SDK |
| `pyproject.toml` | Dependencies and entry point |

## Environment variables (in `.env`)

```
AZURE_OPENAI_ENDPOINT=https://....openai.azure.com/
AZURE_OPENAI_API_KEY=...
AZURE_OPENAI_DEPLOYMENT=gpt-4o
AZURE_OPENAI_API_VERSION=2024-08-01-preview
BRAVE_API_KEY=...           # optional — enables Brave Search MCP
```

`.env` is gitignored. Never commit API keys.

## Common commands

```bash
# After any source change — reinstall the global CLI
python3 -m pipx reinstall jarvis

# Run from this directory (picks up this JARVIS.md automatically)
jarvis

# Commit and push
git add -p
git commit -m "..."
git push origin main

# Check what's installed
pipx list

# View session logs
ls ~/.jarvis/logs/
cat ~/.jarvis/logs/$(date +%Y-%m-%d).jsonl | jq .
```

## How to add a new tool

1. Create `jarvis/tools/my_tool.py` subclassing `BaseTool`:
   ```python
   from .base import BaseTool
   class MyTool(BaseTool):
       name = "my_tool"
       description = "Does X given Y."
       parameters = {
           "type": "object",
           "properties": {"arg": {"type": "string", "description": "..."}},
           "required": ["arg"],
       }
       def execute(self, args: dict) -> str:
           return "result"
   ```
2. Import and add to `_REGISTRY` in `jarvis/tools/__init__.py`
3. Reinstall with `python3 -m pipx reinstall jarvis`

## How to add a new slash command

1. Add a block in `commands.py:handle_command()`:
   ```python
   if cmd == "/mycommand":
       # ... do work ...
       return None  # or _EXIT_SENTINEL or f"{_RUN_AGENT_PREFIX}message"
   ```
2. Add an entry to `_HELP_TEXT` at the top of `commands.py`
3. Reinstall

## Known issues / gotchas

- `cd` in `run_command` works (calls `os.chdir()`), but the prompt only updates on the next REPL iteration
- MCP servers connect at startup only — if a server crashes, restart jarvis
- `stream_options: {"include_usage": True}` is required to get real token counts (not estimates) from Azure
- `edit_file` requires `old_string` to appear exactly once in the file — if it appears 0 or 2+ times it returns an error
- The `.env` candidate search order: `cwd/.env` → `~/.jarvis.env` → `~/jarvis/.env` → package root `.env`
- Cost estimates are approximations — Azure pricing may differ from the hardcoded `_PRICING` table in `context.py`

## Improvement ideas

- Multi-file context (`/file` loads one file; could auto-load all files matching a glob)
- Persistent memory across sessions (write key facts to `~/.jarvis/memory.md`, auto-load it)
- Interrupt mid-stream with Ctrl+C to start a new message (currently cancels and shows "Cancelled")
- Auto-compact when context exceeds a token threshold (hook into `token_estimate()`)
- `/undo` command to pop the last assistant + user turn from history
- Test suite — no tests exist yet, `pytest jarvis/tests/` would be the path
- Syntax-highlighted output for code blocks in streaming responses (currently plain markdown)
