# Jarvis repo — loop worker notes

Python CLI coding agent (Azure OpenAI). Source in `jarvis/`, tests in `jarvis/tests/`.
Ignore `build/` and `.venv/` (never edit). Full architecture docs live in JARVIS.md —
do NOT read it unless a step requires it; the notes below cover the common cases.

## You are running unattended

This checkout is a disposable automation workspace and no human can answer you
mid-run. NEVER stop to ask for confirmation — a question ends the run and wastes
the quota batch. Make the call yourself: prefer `git stash -u` over discarding
when unsure about tree state, prefer skipping a step (note why in the log output)
over blocking on approval. The only unrecoverable mistake is pushing red to main,
and branch protection + CI already prevent that.

## Working style (token budget)

- Your quota is the constraint. Spend tokens editing and testing, not exploring:
  read ONLY the files the current step names. Use grep to locate, then read the
  region. Never re-read ROADMAP.md/PARITY.md in full if the step text is in your prompt.
- Tests: `.venv/bin/python -m pytest jarvis/tests -q`. Never commit on red.
- Don't run `pipx reinstall` or start the `jarvis` REPL — CI and the deploy job
  handle installs; the REPL needs Azure credentials and will just waste turns.

## Invariants (break these and tests/review will bounce you)

- New tool → subclass `BaseTool`, register in `jarvis/tools/__init__.py:_REGISTRY`.
- New slash command → `commands.py:handle_command()` + `_HELP_TEXT` entry; every
  handler must `return`.
- All terminal output through `formatter.py` helpers; tools return plain strings,
  errors as `"Error: ..."` strings, never exceptions.
- Config: runtime settings live in `jarvis/settings.py` (Settings dataclass,
  ~/.jarvis/config.toml + project .jarvis.toml overlay). Azure env vars in `config.py`.
- Every behavior change ships WITH a test in the same commit, and updates the
  matching JARVIS.md section (tool table / command list) — a 1-3 line edit, not a rewrite.

## Git

- Branch `feat/roadmap-step-N` → commit → push → `gh pr create` →
  `gh pr checks --watch && gh pr merge --squash --delete-branch` → back to main.
- Commit message: `Roadmap N.M: <what changed>`.
