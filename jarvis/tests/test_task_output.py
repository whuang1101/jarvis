from __future__ import annotations

from jarvis import tasks as tasks_mod
from jarvis.tools.task_output import TaskOutputTool


def test_unknown_task_id_returns_error(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(tasks_mod, "TASKS_DIR", tmp_path)
    result = TaskOutputTool().execute({"task_id": "nonexistent"})
    assert result.startswith("Error: no such task")
