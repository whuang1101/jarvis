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
| Todo list the agent maintains (TaskCreate-style) with live checklist UI | ❌ | ROADMAP 5.1 |
| Subagents (spawn isolated agent for a subtask, return summary) | ❌ | ROADMAP 5.4 |
| Interrupt stream with Esc/Ctrl+C, keep partial, steer mid-task | 🟡 | Ctrl+C keeps partial; no "steer while running" queued input |
| Auto-compaction of context | ✅ | at ~25K est. tokens |
| Context window usage indicator | ✅ | token tag in input bar |
| Prompt caching / cost optimization | ❌ | N/A-ish on Azure; could cache system prompt |

## Tools

| Feature | Status | Notes |
|---|---|---|
| Read (with offset/limit, line numbers) | ✅ | |
| Read images (vision input) | ❌ | paths/clipboard → vision content parts |
| Read PDFs / Jupyter notebooks | ✅ | `read_file` auto-detects `.ipynb`/`.pdf` |
| Write / Edit with unique-anchor + replace_all | 🟡 | no replace_all yet (ROADMAP 5.3) |
| Bash with persistent cwd | ✅ | os.chdir on `cd` |
| Bash background tasks (run_in_background, task output tool) | ❌ | ROADMAP 4.4 |
| Streaming command output while running | ❌ | ROADMAP 4.3 |
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
| Allow/deny rules with patterns, e.g. Bash(git *) | ❌ | ROADMAP 2.3 |
| "Yes, don't ask again" option that persists | ❌ | ROADMAP 2.4 |
| Settings hierarchy (user / project / local overrides) | ❌ | ROADMAP 2.1–2.2 |
| Sandboxed command execution | ❌ | ROADMAP Phase 6 / security section of TODO.md |
| Sensitive-file protection (.env etc. excluded from reads) | ✅ | |

## Sessions & persistence

| Feature | Status | Notes |
|---|---|---|
| --continue / --resume past sessions | ❌ | ROADMAP 3.2–3.3 |
| Session picker with metadata | ❌ | ROADMAP 3.3 |
| /rewind (checkpoint & restore conversation + files) | ❌ | big; file checkpoints via git stash-like shadow |
| Persistent memory file (auto-loaded) | ✅ | ~/.jarvis/memory.md |
| # shortcut to append a memory quickly | ✅ | `#text` at prompt → memory.md |
| Project context file (CLAUDE.md ≈ JARVIS.md) with parent-dir walk | ✅ | |
| @file mentions to pull files into a message | ❌ | parse `@path` in input, attach content |
| Session logs / transcript export | ✅ | JSONL + /save |

## Headless / scripting

| Feature | Status | Notes |
|---|---|---|
| -p one-shot mode | ❌ | ROADMAP 3.1 |
| --output-format json / stream-json | ❌ | after 3.1 |
| Pipe stdin as prompt (`cat err | jarvis -p "fix"`) | ❌ | after 3.1 |
| --max-turns, --model flags | ❌ | after 3.1 |
| Exit codes reflecting success/failure | ❌ | after 3.1 |

## Extensibility

| Feature | Status | Notes |
|---|---|---|
| Custom slash commands from markdown files | ❌ | ROADMAP 4.1 |
| Hooks (PreToolUse / PostToolUse / Stop, with blocking exit codes) | ❌ | ROADMAP 4.2 |
| MCP servers (stdio) | ✅ | GitHub / Azure / Brave at startup |
| MCP: add/remove/list at runtime, project .mcp.json config | ❌ | servers are hardcoded; `/mcp` command + config file |
| MCP reconnect on crash | ❌ | TODO.md robustness item |
| Skills (folder of markdown capabilities, auto-triggered) | ❌ | ambitious; markdown commands first |
| Plugins / marketplaces | ❌ | out of scope for now |
| Output styles / themes | ❌ | /theme in TODO.md |
| Status line customization | ❌ | input-bar top border is the hook point |

## Git & GitHub workflows

| Feature | Status | Notes |
|---|---|---|
| git status/diff/log tools | ✅ | |
| Commit with generated message (through permission gate) | ❌ | ROADMAP 5.5 |
| PR creation with generated title/body | ❌ | ROADMAP 5.5 |
| PR review (/review) | ❌ | ROADMAP 5.5 |
| GitHub MCP integration | ✅ | 26 tools when gh is authed |

## Interactive UX

| Feature | Status | Notes |
|---|---|---|
| Welcome panel, ⏺ bullets, ⎿ tool results, boxed input bar | ✅ | restyled 2026-07 |
| Input history (up arrow), tab hints | 🟡 | readline history; no fuzzy command autocomplete |
| Slash-command autocomplete menu as you type / | ❌ | needs raw-mode input loop (prompt_toolkit) |
| Multiline input (backslash or ``` blocks) | ❌ | TODO.md |
| Vim mode / keybindings | ❌ | low priority |
| Syntax-highlighted code fences in streamed output | 🟡 | Markdown render highlights after stream; not during |
| Spinner with elapsed time + token count while thinking | 🟡 | plain spinner |
| Desktop notifications when a long task finishes | ❌ | TODO.md notifications section |
| /doctor style self-diagnostics | ❌ | checks: env vars, MCP health, pipx install, test suite |
| /usage, /model, /compact, /clear, /help | ✅ | |

## Autonomy loop instruction

When every ROADMAP.md checkbox is done:
1. Pick the topmost ❌ in this file that is feasible without human-only resources
   (no paid signups, no interactive login).
2. Append a new phase to ROADMAP.md: 2–6 concrete steps in the established format
   (files to touch, exact behavior, a *Verify:* line each).
3. Flip this table's ❌ to 🟡/✅ only when the roadmap steps land on main.
4. Then continue the normal per-step contract.
