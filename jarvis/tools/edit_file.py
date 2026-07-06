from __future__ import annotations

from pathlib import Path
from typing import Any

from .base import BaseTool


def occurrence_lines(content: str, substring: str) -> list[int]:
    """1-based line number of each non-overlapping occurrence of substring in content."""
    lines = []
    start = 0
    while True:
        idx = content.find(substring, start)
        if idx == -1:
            break
        lines.append(content.count("\n", 0, idx) + 1)
        start = idx + len(substring)
    return lines


def multi_occurrence_error(path: str, content: str, old_string: str, count: int) -> str:
    line_list = ", ".join(str(n) for n in occurrence_lines(content, old_string))
    return (
        f"Error: old_string appears {count} times in {path} (lines {line_list}). "
        "Add more surrounding context to make it unique, or pass replace_all=true to replace them all."
    )


class EditFileTool(BaseTool):
    name = "edit_file"
    description = (
        "Replace an exact string in a file with new content. "
        "Prefer this over write_file for targeted changes to existing files — "
        "it only touches the lines that change. "
        "old_string must appear exactly once in the file, unless replace_all is set."
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
            "replace_all": {
                "type": "boolean",
                "description": "Replace every occurrence of old_string instead of requiring a single unique match. Defaults to false.",
            },
        },
        "required": ["path", "old_string", "new_string"],
    }

    def execute(self, args: dict[str, Any]) -> str:
        path: str = args["path"]
        old_string: str = args["old_string"]
        new_string: str = args["new_string"]
        replace_all: bool = bool(args.get("replace_all", False))

        try:
            content = Path(path).read_text(encoding="utf-8")
        except FileNotFoundError:
            return f"Error: {path} not found"
        except OSError as e:
            return f"Error reading {path}: {e}"

        if old_string not in content:
            return f"Error: old_string not found in {path}. Make sure the text matches exactly, including whitespace and indentation."

        count = content.count(old_string)
        if count > 1 and not replace_all:
            return multi_occurrence_error(path, content, old_string, count)

        new_content = (
            content.replace(old_string, new_string)
            if replace_all
            else content.replace(old_string, new_string, 1)
        )
        try:
            Path(path).write_text(new_content, encoding="utf-8")
            if replace_all and count > 1:
                return f"Edited {path} ({count} replacements)"
            return f"Edited {path}"
        except OSError as e:
            return f"Error writing {path}: {e}"
