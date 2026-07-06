from __future__ import annotations

from pathlib import Path
from typing import Any

from .base import BaseTool

_MAX_RESULTS = 200


class GlobFilesTool(BaseTool):
    name = "glob"
    description = "Find files matching a glob pattern (e.g. '**/*.py' or 'src/*.ts'), newest first."
    parameters = {
        "type": "object",
        "properties": {
            "pattern": {"type": "string", "description": "Glob pattern to match, e.g. '**/*.py'."},
            "path": {"type": "string", "description": "Root directory to search from. Defaults to current directory.", "default": "."},
        },
        "required": ["pattern"],
    }

    def execute(self, args: dict[str, Any]) -> str:
        pattern: str = args["pattern"]
        path_str: str = args.get("path", ".")
        root = Path(path_str).expanduser()
        if not root.is_dir():
            return f"Error: path not found: {path_str}"

        try:
            matches = [
                p for p in root.glob(pattern)
                if p.is_file() and not any(part.startswith(".") for part in p.relative_to(root).parts)
            ]
        except (ValueError, OSError) as e:
            return f"Error: {e}"

        if not matches:
            return f"No files match {pattern}"

        matches.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        total = len(matches)
        matches = matches[:_MAX_RESULTS]
        lines = [str(p.relative_to(root)) for p in matches]
        if total > _MAX_RESULTS:
            lines.append(f"[... {total - _MAX_RESULTS} more]")
        return "\n".join(lines)
