# Jarvis — Improvement Backlog

Check this file before suggesting new features. Mark items `[x]` when done and note what file was changed.

---

## UX / Quality of Life

- [ ] **`/undo`** — pop the last user + assistant turn from `context._history`
- [ ] **`/retry`** — resend the last user message through the agent
- [ ] **`/history`** — print the last N exchanges from the current session in a readable format
- [ ] **`/save <file>`** — dump the current conversation to a markdown file
- [ ] **`/copy`** — copy the last assistant response to clipboard via `pbcopy`
- [ ] **`/memory`** — subcommands: `/memory show`, `/memory add <text>`, `/memory clear` to manage `~/.jarvis/memory.md`
- [ ] **Token count in prompt** — show estimated context size in the prompt e.g. `~/jarvis [4.2k] >` using `context.token_estimate()`
- [ ] **Syntax-highlighted streaming output** — detect triple-backtick fences in streamed tokens and render code blocks with Rich `Syntax` instead of plain text

## Robustness

- [ ] **Tool result truncation** — if a tool returns more than 8000 characters, truncate it and append `[truncated — X chars omitted]` so large outputs don't blow up context
- [ ] **`read_file` size guard** — if a file is over 100KB, return a warning instead of dumping the full content into context
- [ ] **`run_command` output truncation** — if stdout/stderr exceeds 50 lines, show the first 25 + last 25 with a `[X lines omitted]` notice
- [ ] **Tool timeout handling** — wrap tool execution in a timeout (currently an unhandled exception crashes the turn)
- [ ] **Auto-compact** — when `context.token_estimate()` exceeds a threshold (e.g. 25K), automatically run compact before the next request instead of just warning
- [ ] **Graceful MCP reconnect** — if an MCP server crashes mid-session, attempt to reconnect instead of silently failing

## Shell Integration

- [ ] **`jfix` zshrc function** — shell function that captures the last command's exit code + stderr and pipes it to `jarvis` as a `/fix` request, so you can type `jfix` after any failed command
- [ ] **`jask` one-shot mode** — `jask "question"` runs a single query and exits without entering the REPL, useful for scripting
- [ ] **`jarvis --cmd "..."` flag** — run a single prompt non-interactively from the CLI

## Features

- [ ] **`/model` lists deployments** — when called with no args, query the Azure API for available deployments instead of just echoing the current one
- [ ] **Multi-file `/file` glob** — `/file src/*.py` loads all matching files at once
- [ ] **Streaming `run_command`** — stream stdout line-by-line as the command runs instead of buffering until completion
- [ ] **`/diff` command** — show all uncommitted git changes in the current repo (alias for `git diff HEAD`)
- [ ] **Git commit helper** — when asked to commit, Jarvis stages relevant files, writes a meaningful message, and runs the commit itself
- [ ] **`/pin <message>`** — add a message to context that persists across `/compact` and `/clear` (e.g. "always use TypeScript strict mode")

## Code Quality

- [ ] **Test suite** — add `jarvis/tests/` with at least unit tests for `permissions.py`, `context.py`, and tool execute methods
- [ ] **`mypy` type checking** — add `mypy` to dev dependencies and fix any type errors
- [ ] **Structured logging** — add log levels to `logger.py` so debug output can be toggled with `--verbose`

---

## Completed

- [x] **Streaming responses** — live token-by-token output via Azure OpenAI stream
- [x] **Tool use loop** — agentic loop with up to 10 tool iterations (`agent.py`)
- [x] **Permission gate** — diff preview + arrow-key Yes/No before file writes (`permissions.py`)
- [x] **Auto mode** — `/auto` skips file approval prompts; destructive commands always ask (`permissions.py`, `commands.py`)
- [x] **Cost tracking** — `/usage` shows tokens + estimated USD cost (`context.py`, `commands.py`)
- [x] **Model switching** — `/model <name>` switches Azure deployment mid-session (`client.py`)
- [x] **`/fix` command** — grabs clipboard and sends error to agent (`commands.py`)
- [x] **`/compact`** — summarize and compress conversation history (`context.py`)
- [x] **`/restart`** — reinstalls package and re-execs process in place (`commands.py`)
- [x] **Session logging** — JSONL logs to `~/.jarvis/logs/YYYY-MM-DD.jsonl` (`logger.py`)
- [x] **MCP integrations** — GitHub, Azure, Brave Search via MCP SDK (`mcp_manager.py`)
- [x] **Persistent memory** — loads `~/.jarvis/memory.md` into system prompt (`context.py`)
- [x] **Message history navigation** — UP arrow recalls previous inputs via `readline` (`cli.py`)
- [x] **Rate limit retry** — exponential backoff on 429 errors (`agent.py`)
- [x] **Context size warning** — warns at 20K estimated tokens and suggests `/compact` (`agent.py`)
- [x] **Directory in prompt** — shows current working directory at all times (`cli.py`)
- [x] **`cd` support** — `run_command` intercepts `cd` and calls `os.chdir()` (`tools/run_command.py`)
- [x] **Git tools** — `git_status`, `git_diff`, `git_log` tools (`tools/git_tools.py`)
- [x] **`edit_file` tool** — targeted string replacement with diff preview (`tools/edit_file.py`)
- [x] **JARVIS.md auto-load** — walks up from cwd to find and inject project context (`cli.py`)
