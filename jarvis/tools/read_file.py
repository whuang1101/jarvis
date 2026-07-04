from __future__ import annotations

import os
from typing import Any

from .base import BaseTool

_TRUNCATE_AT = 10_000
_MAX_FULL_READ_BYTES = 100_000  # over this, require offset/limit


class ReadFileTool(BaseTool):
    name = "read_file"
    description = (
        "Read the contents of a file at the given path. For large files, pass "
        "offset (1-based start line) and limit (number of lines) to read a slice."
    )
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Path to the file to read."},
            "offset": {"type": "integer", "description": "1-based line number to start reading from."},
            "limit": {"type": "integer", "description": "Maximum number of lines to read."},
        },
        "required": ["path"],
    }

    def execute(self, args: dict[str, Any]) -> str:
        path: str = args["path"]
        offset = args.get("offset")
        limit = args.get("limit")

        try:
            size = os.path.getsize(path)
        except FileNotFoundError:
            return f"Error: file not found: {path}"
        except OSError as e:
            return f"Error reading {path}: {e}"

        if size > _MAX_FULL_READ_BYTES and not (offset or limit):
            return (
                f"Error: {path} is {size:,} bytes (over the {_MAX_FULL_READ_BYTES:,}-byte full-read limit). "
                "Use search_files/find_symbol to locate what you need, then re-read with offset and limit."
            )

        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                if offset or limit:
                    start = max(int(offset or 1), 1)
                    count = max(int(limit or 500), 1)
                    lines: list[str] = []
                    for i, line in enumerate(f, start=1):
                        if i < start:
                            continue
                        if len(lines) >= count:
                            break
                        lines.append(f"{i}: {line.rstrip(chr(10))}")
                    if not lines:
                        return f"Error: {path} has fewer than {start} lines."
                    content = "\n".join(lines)
                else:
                    content = f.read()
        except OSError as e:
            return f"Error reading {path}: {e}"

        if len(content) > _TRUNCATE_AT:
            return content[:_TRUNCATE_AT] + f"\n\n[... truncated — output is {len(content)} chars, showing first {_TRUNCATE_AT}]"
        return content
