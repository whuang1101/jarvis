from __future__ import annotations

import os
import subprocess
import uuid
from pathlib import Path

TASKS_DIR = Path.home() / ".jarvis" / "tasks"


def start_background_task(command: str) -> str:
    """Launch `command` detached from the current process, streaming output to a log file.

    Returns a task id usable with `task_status`/`task_log`.
    """
    TASKS_DIR.mkdir(parents=True, exist_ok=True)
    task_id = uuid.uuid4().hex[:8]
    log_path = TASKS_DIR / f"{task_id}.log"
    status_path = TASKS_DIR / f"{task_id}.status"
    status_path.write_text("running")

    # start_new_session detaches the child from our process group/terminal, so it
    # keeps running (and isn't killed) after run_command's own execute() returns.
    notify = (
        "if command -v osascript >/dev/null 2>&1; then "
        f'osascript -e \'display notification "Task {task_id} finished" with title "Jarvis"\'; '
        "fi"
    )
    # A subshell `(...)`, not a `{ ...; }` group, so a bare `exit` in `command`
    # only ends the subshell and still lets us record its status afterward.
    wrapped = (
        f"( {command} ) >> '{log_path}' 2>&1; "
        f"echo $? > '{status_path}.tmp' && mv '{status_path}.tmp' '{status_path}'; "
        f"{notify}"
    )
    subprocess.Popen(
        wrapped,
        shell=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
        start_new_session=True,
        cwd=os.getcwd(),
    )
    return task_id


def task_status(task_id: str) -> str | None:
    """Return 'running', 'done (exit code N)', or None if the task id is unknown."""
    status_path = TASKS_DIR / f"{task_id}.status"
    if not status_path.exists():
        return None
    content = status_path.read_text().strip()
    if content == "running":
        return "running"
    return f"done (exit code {content})"


def task_log(task_id: str) -> str:
    log_path = TASKS_DIR / f"{task_id}.log"
    if not log_path.exists():
        return ""
    return log_path.read_text()
