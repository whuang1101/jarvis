from __future__ import annotations

import os
from typing import Any

from .base import BaseTool


class WriteFileTool(BaseTool):
    name = "write_file"
    description = "Write content to a file at the given path, creating it if it doesn't exist."
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Path to write to."},
            "content": {"type": "string", "description": "Content to write."},
        },
        "required": ["path", "content"],
    }

    def execute(self, args: dict[str, Any]) -> str:
        path: str = args["path"]
        content: str = args["content"]
        try:
            os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            return f"Written {len(content)} chars to {path}"
        except OSError as e:
            return f"Error writing {path}: {e}"
