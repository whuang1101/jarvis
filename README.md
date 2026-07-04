# Jarvis

A self-hosted, **self-improving** CLI coding assistant, in the spirit of Claude Code,
built on Azure OpenAI. Jarvis is a streaming agentic REPL with tool use, MCP
integrations, a permission/diff gate, plan mode, auto mode, session logging, cost
tracking, and persistent memory — and it runs *inside its own repository*, so it can
read, edit, test, reinstall, and restart its own source code.

```
~/jarvis [4.2k] AUTO > add a /diff command that shows uncommitted changes
```

## What makes it different

Jarvis is designed to improve itself. The repo contains:

- **`JARVIS.md`** — the project map Jarvis loads as context every session, including a
  "Self-improvement workflow": find → read → edit → verify → test → update docs →
  reinstall → restart (with resume state, so it picks up where it left off).
- **`ROADMAP.md`** — an ordered, step-by-step plan toward a Claude-Code-level
  experience, written so that Jarvis (or any capable model) can execute it one step at
  a time. Phases 0–1 (test safety net, agent-loop robustness) were done by hand;
  Phases 2–5 are Jarvis's job.
- **`TODO.md`** — the raw feature/bug backlog the roadmap draws from.
- **`jarvis/tests/`** — the test suite (`/selftest` from the REPL) that gates every
  self-modification before Jarvis reinstalls itself.

## Features

| Area | What you get |
|---|---|
| Agentic loop | Streaming responses (Rich live Markdown), up to 40 tool iterations per turn, progress summary if the cap is hit |
| Tools | read/write/edit file, run command, dir tree, grep search, symbol finder, git status/diff/log, web search/fetch/extract, package lookup |
| Safety | Diff preview + arrow-key approval before file writes; destructive shell commands (`rm`, `sudo`, `git reset --hard`, …) always prompt, even in auto mode |
| Robustness | Tool results capped at 8K chars, 60s tool timeouts, auto-compaction at ~25K tokens, rate-limit retries, Ctrl+C keeps partial output |
| Modes | `/plan` (draft a plan, wait for `/go`), `/auto` (apply file edits without prompting) |
| MCP | GitHub, Azure, and Brave Search MCP servers auto-connect at startup when credentials exist |
| Sessions | JSONL event logs in `~/.jarvis/logs/`, `/usage` token + cost tracking, `/compact`, `/save`, `/memory` |
| Self-hosting | `/restart` reinstalls via pipx and re-execs in place; in auto mode it writes a resume file and continues its task after restarting |

## Install

Requires Python ≥ 3.11, [pipx](https://pipx.pypa.io), and an Azure OpenAI deployment.

```bash
git clone https://github.com/whuang1101/jarvis.git ~/jarvis
cd ~/jarvis
cat > .env <<'ENV'
AZURE_OPENAI_ENDPOINT=https://<resource>.openai.azure.com/
AZURE_OPENAI_API_KEY=<key>
AZURE_OPENAI_DEPLOYMENT=gpt-4o
AZURE_OPENAI_API_VERSION=2024-08-01-preview
ENV
pipx install -e .
jarvis
```

Optional: `BRAVE_API_KEY` in `.env` enables Brave Search MCP; `gh auth login` enables
GitHub MCP; `az login` enables Azure MCP.

## Commands

`/help /history /retry /undo /clear /compact /usage /model /file /run /plan /go
/cancel /restart /auto /fix /copy /save /memory /init /selftest /exit`

## Making Jarvis improve itself

Start Jarvis anywhere under the repo (so `JARVIS.md` loads), then:

```
/auto
Work through ROADMAP.md autonomously. Do one step at a time, in order.
```

Jarvis will pick the next unchecked step, implement it, run `/selftest`, mark the box,
update `JARVIS.md`, reinstall, restart, and continue — committing a PR every few steps.
See the header of `ROADMAP.md` for the exact operating rules, and
`JARVIS.md → Self-improvement workflow` for the edit loop it follows.

Because auto mode never bypasses the destructive-command gate, and every reinstall is
preceded by the test suite, a broken self-edit fails loudly instead of silently
corrupting the tool.

## Development

```bash
python3 -m pytest jarvis/tests -q     # test suite (also: /selftest in the REPL)
python3 -m pipx reinstall jarvis      # pick up source changes
cat ~/.jarvis/logs/$(date +%F).jsonl | jq .   # inspect a session
```

Architecture, key flows, and conventions are documented in `JARVIS.md` — that file is
both the human docs and the context Jarvis itself operates from, so keep it accurate.
