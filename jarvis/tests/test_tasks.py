from __future__ import annotations

import time

from jarvis import tasks as tasks_mod


def _wait_for_done(task_id: str, timeout: float = 5.0) -> str:
    deadline = time.monotonic() + timeout
    status = tasks_mod.task_status(task_id)
    while status == "running" and time.monotonic() < deadline:
        time.sleep(0.05)
        status = tasks_mod.task_status(task_id)
    return status


def test_start_background_task_returns_immediately(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(tasks_mod, "TASKS_DIR", tmp_path)
    start = time.monotonic()
    task_id = tasks_mod.start_background_task("sleep 0.5 && echo done")
    elapsed = time.monotonic() - start
    assert elapsed < 0.3
    assert tasks_mod.task_status(task_id) is not None


def test_background_task_completes_and_captures_log(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(tasks_mod, "TASKS_DIR", tmp_path)
    task_id = tasks_mod.start_background_task("echo hello")
    status = _wait_for_done(task_id)
    assert status == "done (exit code 0)"
    assert "hello" in tasks_mod.task_log(task_id)


def test_background_task_captures_nonzero_exit(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(tasks_mod, "TASKS_DIR", tmp_path)
    task_id = tasks_mod.start_background_task("exit 7")
    status = _wait_for_done(task_id)
    assert status == "done (exit code 7)"


def test_unknown_task_status_is_none(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(tasks_mod, "TASKS_DIR", tmp_path)
    assert tasks_mod.task_status("nonexistent") is None
    assert tasks_mod.task_log("nonexistent") == ""
