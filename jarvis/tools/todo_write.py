from __future__ import annotations

from typing import Any

from .base import BaseTool
from ..formatter import print_todo_list

_STATUSES = ("pending", "in_progress", "completed")


class TodoWriteTool(BaseTool):
    name = "todo_write"
    description = (
        "Create or update the visible task list for multi-step work. Always pass the FULL "
        "list of todos (not a diff) — each call replaces the previous list. Use this to plan "
        "out steps up front and mark them in_progress/completed as you go, so the user can "
        "see progress."
    )
    parameters = {
        "type": "object",
        "properties": {
            "todos": {
                "type": "array",
                "description": "The complete current task list.",
                "items": {
                    "type": "object",
                    "properties": {
                        "content": {"type": "string", "description": "Short task description."},
                        "status": {"type": "string", "enum": list(_STATUSES)},
                    },
                    "required": ["content", "status"],
                },
            },
        },
        "required": ["todos"],
    }

    def execute(self, args: dict[str, Any]) -> str:
        todos = args.get("todos")
        if not isinstance(todos, list):
            return "Error: todos must be a list"

        normalized: list[dict[str, str]] = []
        for item in todos:
            if not isinstance(item, dict):
                return "Error: each todo must be an object with content and status"
            content = str(item.get("content", "")).strip()
            if not content:
                return "Error: every todo needs a non-empty content string"
            status = item.get("status", "pending")
            if status not in _STATUSES:
                return f"Error: invalid status '{status}' (must be one of {_STATUSES})"
            normalized.append({"content": content, "status": status})

        print_todo_list(normalized)
        done = sum(1 for t in normalized if t["status"] == "completed")
        return f"Todo list updated ({done}/{len(normalized)} completed)."
