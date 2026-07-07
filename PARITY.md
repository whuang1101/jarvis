# Claude Code Feature Parity Catalogue

A comprehensive inventory of what Claude Code offers, with Jarvis's status on each.
This is the **idea backlog for the autonomous loop**: when ROADMAP.md has no
unchecked steps left, pick the highest-value ❌ item here, write it up as new
roadmap steps (same format, with files + verification), append them to ROADMAP.md,
and implement.

Legend: ✅ Jarvis has it · 🟡 partial · ❌ missing

## Core agent loop

| Feature | Status | Notes |
|---|---|---|
| Streaming responses with live rendering | ✅ | Rich Live markdown |
| Multi-step tool loop (dozens of iterations) | ✅ | 40 cap + progress summary |
| Extended thinking / reasoning display | ✅ | dimmed italic live block, gated by `show_thinking` |
| Parallel tool calls in one turn | 🟡 | executed sequentially; could thread independent calls |
| Todo list the agent maintains (TaskCreate-style) with live checklist UI | ✅ | full re-render panel, not an in-place `Live` widget (a second concurrent `Live` would fight the streaming-markdown `Live`) |
| Subagents (spawn isolated agent for a subtask, return summary) | ✅ | `spawn_agent` read-only subagent, ROADMAP 5.4 |
| Interrupt stream with Esc/Ctrl+C, keep partial, steer mid-task | 🟡 | Ctrl+C keeps partial; no "steer while running" queued input |
| Auto-compaction of context | ✅ | at ~25K est. tokens |
| Context window usage indicator | ✅ | token tag in input bar |
| Prompt caching / cost optimization | 🟡 | surfaces Azure `cached_tokens` in `/usage` + JSON, cost discounted; relies on Azure's automatic prefix caching (no explicit cache-control API) |

## Tools

| Feature | Status | Notes |
|---|---|---|
| Read (with offset/limit, line numbers) | ✅ | |
| Read images (vision input) | ✅ | `read_file` image detection + `image_url` attachment, gated by `vision` setting |
| Read PDFs / Jupyter notebooks | ✅ | `read_file` auto-detects `.ipynb`/`.pdf` |
| Write / Edit with unique-anchor + replace_all | 🟡 | no replace_all yet (ROADMAP 5.3) |
| Bash with persistent cwd | ✅ | os.chdir on `cd` |
| Bash background tasks (run_in_background, task output tool) | ✅ | ROADMAP 4.4 |
| Streaming command output while running | ✅ | ROADMAP 4.3 |
| Glob (find files by pattern) | ✅ | `glob_files.py` |
| Grep (regex, context lines, filters by type/glob) | 🟡 | search_files is plain grep -rn; no -A/-B/type filters |
| WebSearch | ✅ | DuckDuckGo |
| WebFetch (URL → markdown extraction) | ✅ | trafilatura |
| Symbol lookup | ✅ | find_symbol (beyond CC's grep, actually) |

## Permissions & safety

| Feature | Status | Notes |
|---|---|---|
| Diff preview before every file change | ✅ | |
| Permission modes (default / acceptEdits / plan / bypassPermissions) | 🟡 | auto + plan exist; no full bypass, no per-session mode switch UI |
| Allow/deny rules with patterns, e.g. Bash(git *) | ✅ | ROADMAP 2.3 |
| "Yes, don't ask again" option that persists | ✅ | ROADMAP 2.4 |
| Settings hierarchy (user / project / local overrides) | ✅ | ROADMAP 2.1–2.2 |
| Sandboxed command execution | 🟡 | opt-in `bwrap` sandbox (read-only root, writable project dir, net off by default); Linux-only, deny-by-default when bwrap missing; `/sandbox` toggle |
| Sensitive-file protection (.env etc. excluded from reads) | ✅ | |

## Sessions & persistence

| Feature | Status | Notes |
|---|---|---|
| --continue / --resume past sessions | ✅ | ROADMAP 3.2–3.3 |
| Session picker with metadata | ✅ | ROADMAP 3.3 |
| /rewind (checkpoint & restore conversation + files) | 🟡 | session-scoped in-memory checkpoints, not cross-session; file restore covers tracked modifications only |
| Persistent memory file (auto-loaded) | ✅ | ~/.jarvis/memory.md |
| # shortcut to append a memory quickly | ✅ | `#text` at prompt → memory.md |
| Project context file (CLAUDE.md ≈ JARVIS.md) with parent-dir walk | ✅ | |
| @file mentions to pull files into a message | ✅ | `expand_file_mentions` inlines `@path` text; image `@mentions` route to vision |
| Session logs / transcript export | ✅ | JSONL + /save |

## Headless / scripting

| Feature | Status | Notes |
|---|---|---|
| -p one-shot mode | ✅ | ROADMAP 3.1 |
| --output-format json / stream-json | ✅ | init + result events only; per-tool event lines are a follow-up |
| Pipe stdin as prompt (`cat err | jarvis -p "fix"`) | ✅ | ROADMAP 13 |
| --max-turns, --model flags | ✅ | ROADMAP 14 |
| Exit codes reflecting success/failure | 🟡 | one-shot `sys.exit(1)` on unhandled error; no per-turn failure code |

## Extensibility

| Feature | Status | Notes |
|---|---|---|
| Custom slash commands from markdown files | ✅ | ROADMAP 4.1 |
| Hooks (PreToolUse / PostToolUse / Stop, with blocking exit codes) | ✅ | ROADMAP 4.2 |
| MCP servers (stdio) | ✅ | GitHub / Azure / Brave at startup |
| MCP: add/remove/list at runtime, project .mcp.json config | 🟡 | `/mcp` list/add/remove + `.mcp.json` startup loading; runtime-added servers are session-scoped |
| MCP reconnect on crash | ✅ | transparent respawn + single retry in `_call_tool`, gated by `mcp_auto_reconnect` |
| Skills (folder of markdown capabilities, auto-triggered) | 🟡 | name+description catalog injected into the system prompt from `~/.jarvis/skills/` + project `.jarvis/skills/`; model loads full body on demand via the `skill` tool; `/skills` lists them |
| Plugins / marketplaces | ❌ | out of scope for now |
| Output styles / themes | ✅ | `/theme` + `theme` setting (Rich syntax themes) |
| Status line customization | 🟡 | shell command in `statusline` setting; receives cwd/tokens/mode JSON on stdin, first stdout line becomes the input-bar top border, falls back to default on error; `/statusline` sets it |

## Git & GitHub workflows

| Feature | Status | Notes |
|---|---|---|
| git status/diff/log tools | ✅ | |
| Commit with generated message (through permission gate) | ✅ | `/commit`, ROADMAP 5.5 |
| PR creation with generated title/body | ✅ | `/pr` gathers branch + commits + diff, agent writes title/body and runs `gh pr create` |
| PR review (/review) | ✅ | `/review [pr#]`, ROADMAP 5.5 |
| GitHub MCP integration | ✅ | 26 tools when gh is authed |

## Interactive UX

| Feature | Status | Notes |
|---|---|---|
| Welcome panel, ⏺ bullets, ⎿ tool results, boxed input bar | ✅ | restyled 2026-07 |
| Input history (up arrow), tab hints | 🟡 | readline history; no fuzzy command autocomplete |
| Slash-command autocomplete menu as you type / | ✅ | prompt_toolkit input bar shows a live `/`-command dropdown on TTY; falls back to readline `input()` when piped or prompt_toolkit missing |
| Multiline input (backslash or ``` blocks) | ✅ | `\`-continuation + ```-fenced blocks joined by `_read_full_input`; continuation lines routed through a completer-free prompt_toolkit session on a TTY |
| Vim mode / keybindings | ✅ | prompt_toolkit `vi_mode` on the TTY input bar; `/vim [on|off]` toggle + persisted `vi_mode` setting |
| Syntax-highlighted code fences in streamed output | 🟡 | Markdown render highlights after stream; not during |
| Spinner with elapsed time + token count while thinking | 🟡 | plain spinner |
| Desktop notifications when a long task finishes | ✅ | `notify.py` fires osascript/notify-send (terminal-bell fallback) when an interactive turn finishes; gated by `notify` + `notify_min_seconds` settings |
| /doctor style self-diagnostics | ✅ | `/doctor` runs `doctor.run_diagnostics()`: Azure creds, MCP health, pytest/mypy tooling |
| /usage, /model, /compact, /clear, /help | ✅ | |

## Autonomy loop instruction

When every ROADMAP.md checkbox is done:
1. Pick the topmost ❌ in this file that is feasible without human-only resources
   (no paid signups, no interactive login).
2. Append a new phase to ROADMAP.md: 2–6 concrete steps in the established format
   (files to touch, exact behavior, a *Verify:* line each).
3. Flip this table's ❌ to 🟡/✅ only when the roadmap steps land on main.
4. Then continue the normal per-step contract.
