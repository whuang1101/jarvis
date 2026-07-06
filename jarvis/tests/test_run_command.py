from __future__ import annotations

import os
import re
import time
from unittest.mock import patch

from jarvis import tasks as tasks_mod
from jarvis.tools.run_command import RunCommandTool
from jarvis.tools.task_output import TaskOutputTool


def test_captures_stdout() -> None:
    result = RunCommandTool().execute({"command": "echo hello"})
    assert "hello" in result


def test_captures_stderr_and_exit_code() -> None:
    result = RunCommandTool().execute({"command": "echo oops 1>&2; exit 3"})
    assert "[stderr]" in result
    assert "oops" in result
    assert "[exit code: 3]" in result


def test_streams_output_live() -> None:
    """Lines must be printed as they're produced, not buffered until the command exits."""
    timestamps: list[float] = []

    def _record(line: str, stderr: bool = False) -> None:
        timestamps.append(time.monotonic())

    with patch("jarvis.tools.run_command.print_streamed_line", side_effect=_record):
        start = time.monotonic()
        RunCommandTool().execute({"command": "echo a && sleep 0.3 && echo b"})

    assert len(timestamps) == 2
    # The second line should land noticeably after the command started, not all at once at exit.
    assert timestamps[1] - timestamps[0] >= 0.2
    assert timestamps[0] - start < 0.2


def test_cd_still_works() -> None:
    original = os.getcwd()
    try:
        result = RunCommandTool().execute({"command": "cd /tmp"})
        assert result.startswith("Changed directory to")
    finally:
        os.chdir(original)


def test_background_returns_task_id_immediately(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(tasks_mod, "TASKS_DIR", tmp_path)
    start = time.monotonic()
    result = RunCommandTool().execute({"command": "sleep 0.5", "background": True})
    elapsed = time.monotonic() - start

    assert elapsed < 0.3
    assert "Started background task" in result
    task_id = re.search(r"background task (\w+)", result).group(1)

    deadline = time.monotonic() + 5
    status = tasks_mod.task_status(task_id)
    while status == "running" and time.monotonic() < deadline:
        time.sleep(0.05)
        status = tasks_mod.task_status(task_id)
    assert status == "done (exit code 0)"


def test_background_task_readable_via_task_output(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(tasks_mod, "TASKS_DIR", tmp_path)
    result = RunCommandTool().execute({"command": "echo hi", "background": True})
    task_id = re.search(r"background task (\w+)", result).group(1)

    deadline = time.monotonic() + 5
    output = TaskOutputTool().execute({"task_id": task_id})
    while "[status: running]" in output and time.monotonic() < deadline:
        time.sleep(0.05)
        output = TaskOutputTool().execute({"task_id": task_id})

    assert "[status: done (exit code 0)]" in output
    assert "hi" in output
