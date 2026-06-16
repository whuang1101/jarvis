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
- [ ] **`/theme`** — let user switch Rich syntax highlighting theme (monokai, dracula, etc.)
- [ ] **Multiline input** — detect when user types `\` at end of line or opens a triple-backtick block and allow multi-line input before sending

## Plan Mode

- [ ] **`/plan` mode** — before executing, Jarvis drafts a step-by-step plan and shows it to the user for approval before touching any files or running any commands. Exit plan mode with `/go` to execute or `/cancel` to abort
- [ ] **Plan display** — show the plan as a numbered checklist, check off each step as it completes
- [ ] **Step-level approval** — in plan mode, optionally approve each step individually rather than the whole plan at once

## Session Management

- [ ] **Session resume** — on startup, offer to resume the most recent session from the JSONL log in `~/.jarvis/logs/`
- [ ] **Named sessions** — `jarvis --session <name>` to start or resume a named session
- [ ] **`/sessions`** — list past sessions with date, message count, and first user message
- [ ] **Session search** — `jarvis --search "query"` to find past sessions by content
- [ ] **Transcript export** — `/save` exports as markdown; add HTML export option for sharing

## Robustness

- [ ] **Tool result truncation** — if a tool returns more than 8000 characters, truncate it and append `[truncated — X chars omitted]` so large outputs don't blow up context
- [ ] **`read_file` size guard** — if a file is over 100KB, return a warning instead of dumping the full content into context
- [ ] **`run_command` output truncation** — if stdout/stderr exceeds 50 lines, show the first 25 + last 25 with a `[X lines omitted]` notice
- [ ] **Tool timeout handling** — wrap tool execution in a configurable timeout; return an error string instead of crashing the turn
- [ ] **Auto-compact** — when `context.token_estimate()` exceeds 25K, automatically compact before the next request instead of just warning
- [ ] **Graceful MCP reconnect** — if an MCP server crashes mid-session, attempt to reconnect instead of silently failing
- [ ] **Offline detection** — detect no internet and disable web tools gracefully instead of erroring

## Shell Integration

- [ ] **`jfix` zshrc function** — captures last command exit code + stderr and pipes to Jarvis as a `/fix` request; type `jfix` after any failed command
- [ ] **`jask` one-shot mode** — `jask "question"` runs a single query and exits, useful for scripting
- [ ] **`jarvis --cmd "..."`** — run a single prompt non-interactively from the CLI
- [ ] **`jarvis --file <path>`** — start session with a file already loaded into context
- [ ] **Shell hook** — optional zshrc hook that captures every failed command (exit code != 0) and makes it available for `/fix` without needing to copy-paste

## Git & Code Workflows

- [ ] **Git commit helper** — stage files, generate a meaningful commit message from the diff, and commit in one shot
- [ ] **PR creation** — `gh pr create` with auto-generated title and body based on branch diff
- [ ] **PR review** — given a PR number or URL, fetch the diff and review it for bugs, style, and issues
- [ ] **`/diff` command** — show all uncommitted changes in the current repo
- [ ] **Merge conflict resolution** — detect conflict markers in files and help resolve them
- [ ] **Branch management** — create, switch, and list branches; suggest branch names based on task
- [ ] **Changelog generation** — generate a changelog from `git log` between two refs
- [ ] **Release helper** — tag a version, generate release notes, push tag

## File & Code Intelligence

- [ ] **Multi-file `/file` glob** — `/file src/*.py` loads all matching files at once
- [ ] **`/pin <message>`** — add a message that persists across `/compact` and `/clear`
- [ ] **Multi-file refactor** — rename a symbol across all files in the project using search + replace
- [ ] **Import fixer** — detect missing or unused imports and fix them automatically
- [ ] **`grep_file` tool** — grep within a specific file (faster than `search_files` for single-file pattern matching)
- [ ] **Image/screenshot support** — accept image paths or clipboard images and send them to the model as vision input
- [ ] **PDF reading** — extract text from PDFs and load into context
- [ ] **Notebook support** — read and edit Jupyter `.ipynb` files cell by cell
- [ ] **Semantic code search** — search by meaning ("where is auth handled?") not just text pattern

## Running & Testing

- [ ] **Streaming `run_command`** — stream stdout line-by-line as the command runs instead of buffering
- [ ] **Test runner** — detect the test framework (pytest, jest, etc.) and run tests, capturing failures into context for fixing
- [ ] **Test generation** — given a function or file, generate a test suite for it
- [ ] **Code coverage** — run tests with coverage and show which lines are uncovered
- [ ] **Linter integration** — run the project linter (ruff, eslint, etc.) and auto-fix issues
- [ ] **Formatter integration** — run black/prettier/gofmt and apply changes via `edit_file`
- [ ] **Watch mode** — `jarvis --watch` reruns the last command whenever a file changes

## Hooks & Extensibility

- [ ] **Pre-tool hooks** — user-configurable shell commands that run before specific tools execute (e.g. run a linter before any file write)
- [ ] **Post-tool hooks** — shell commands that run after a tool completes (e.g. auto-format after write_file)
- [ ] **Custom slash commands** — load user-defined commands from `~/.jarvis/commands/` — each is a markdown file with a prompt template
- [ ] **Plugin system** — allow third-party tools to be loaded from a `jarvis_plugins` entry point
- [ ] **Tool result transforms** — pipeline a tool's output through a shell command before it hits context (e.g. `jq` JSON, `head -n 50`)

## Notifications & Background Work

- [ ] **macOS notification** — send a system notification via `osascript` when a long-running task completes
- [ ] **Background command** — run a shell command in the background and notify when done, without blocking the REPL
- [ ] **Progress indicators** — for multi-step tasks, show a progress bar or step counter alongside the spinner

## Configuration & Settings

- [ ] **`~/.jarvis/config.toml`** — persistent settings file for things like default model, auto mode preference, token warning threshold, max tool iterations
- [ ] **`/config`** — show and edit config values from within the REPL
- [ ] **`/model` lists deployments** — query the Azure API for available deployments when called with no args
- [ ] **Per-project settings** — support a `.jarvis.toml` in the project root for project-specific overrides
- [ ] **Permission rules** — allow/deny specific tools or command patterns permanently in config without always prompting

## Security & Safety

- [ ] **Path sandboxing** — option to restrict file tools to the current working directory tree only
- [ ] **Command allowlist/blocklist** — configurable lists of commands that are always allowed or always blocked
- [ ] **Secrets scanner** — before writing a file, scan for patterns that look like API keys or passwords and warn
- [ ] **Dry-run mode** — `jarvis --dry-run` shows what would happen without executing any tools

## Code Quality

- [ ] **Test suite** — `jarvis/tests/` with unit tests for `permissions.py`, `context.py`, and all tool `execute()` methods
- [ ] **`mypy` type checking** — add `mypy` to dev dependencies and fix type errors
- [ ] **Structured logging** — log levels in `logger.py`, toggle with `--verbose`
- [ ] **`--debug` flag** — print every tool call, argument, and result to stderr for troubleshooting

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
- [x] **Web search** — DuckDuckGo search via `ddgs` (`tools/web_search.py`)
- [x] **Web extract** — fetch and clean page content via `trafilatura` (`tools/web_extract.py`)
