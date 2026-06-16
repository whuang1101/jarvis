from __future__ import annotations

from pathlib import Path
from typing import Any

from .base import BaseTool


class EditFileTool(BaseTool):
    name = "edit_file"
    description = (
        "Replace an exact string in a file with new content. "
        "Prefer this over write_file for targeted changes to existing files — "
        "it only touches the lines that change. "
        "old_string must appear exactly once in the file."
    )
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "File to edit."},
            "old_string": {
                "type": "string",
                "description": "Exact text to replace. Must be unique in the file — include enough surrounding lines to make it unique.",
            },
            "new_string": {
                "type": "string",
                "description": "Replacement text.",
            },
        },
        "required": ["path", "old_string", "new_string"],
    }

    def execute(self, args: dict[str, Any]) -> str:
        path: str = args["path"]
        old_string: str = args["old_string"]
        new_string: str = args["new_string"]

        try:
            content = Path(path).read_text(encoding="utf-8")
        except FileNotFoundError:
            return f"Error: {path} not found"
        except OSError as e:
            return f"Error reading {path}: {e}"

        if old_string not in content:
            return f"Error: old_string not found in {path}. Make sure the text matches exactly, including whitespace and indentation."

        count = content.count(old_string)
        if count > 1:
            return f"Error: old_string appears {count} times in {path}. Add more surrounding context to make it unique."

        new_content = content.replace(old_string, new_string, 1)
        try:
            Path(path).write_text(new_content, encoding="utf-8")
            return f"Edited {path}"
        except OSError as e:
            return f"Error writing {path}: {e}"
