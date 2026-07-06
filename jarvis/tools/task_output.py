from __future__ import annotations

from typing import Any

from .base import BaseTool
from ..tasks import task_log, task_status


class TaskOutputTool(BaseTool):
    name = "task_output"
    description = "Read a background task's status and log output, given the task id returned by run_command(background=true)."
    parameters = {
        "type": "object",
        "properties": {
            "task_id": {"type": "string", "description": "Task id returned by run_command."},
        },
        "required": ["task_id"],
    }

    def execute(self, args: dict[str, Any]) -> str:
        task_id: str = args["task_id"]
        status = task_status(task_id)
        if status is None:
            return f"Error: no such task: {task_id}"
        log = task_log(task_id)
        parts = [f"[status: {status}]"]
        if log:
            parts.append(log)
        return "\n".join(parts)
