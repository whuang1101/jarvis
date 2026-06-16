from __future__ import annotations

from typing import Any

from .base import BaseTool

_TRUNCATE_AT = 10_000


class ReadFileTool(BaseTool):
    name = "read_file"
    description = "Read the contents of a file at the given path."
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Path to the file to read."},
        },
        "required": ["path"],
    }

    def execute(self, args: dict[str, Any]) -> str:
        path: str = args["path"]
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
        except FileNotFoundError:
            return f"Error: file not found: {path}"
        except OSError as e:
            return f"Error reading {path}: {e}"

        if len(content) > _TRUNCATE_AT:
            return content[:_TRUNCATE_AT] + f"\n\n[... truncated — file is {len(content)} chars, showing first {_TRUNCATE_AT}]"
        return content
