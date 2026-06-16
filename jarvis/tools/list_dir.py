from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from .base import BaseTool

_MAX_DEPTH = 2


def _load_gitignore_patterns(directory: str) -> set[str]:
    patterns: set[str] = set()
    gitignore = Path(directory) / ".gitignore"
    if gitignore.exists():
        for line in gitignore.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                patterns.add(line.rstrip("/"))
    return patterns


def _is_ignored(name: str, patterns: set[str]) -> bool:
    return name in patterns or name.startswith(".")


def _build_tree(path: Path, prefix: str, depth: int, patterns: set[str]) -> list[str]:
    if depth > _MAX_DEPTH:
        return []
    try:
        entries = sorted(path.iterdir(), key=lambda p: (p.is_file(), p.name))
    except PermissionError:
        return [f"{prefix}[permission denied]"]

    lines: list[str] = []
    entries = [e for e in entries if not _is_ignored(e.name, patterns)]
    for i, entry in enumerate(entries):
        connector = "└── " if i == len(entries) - 1 else "├── "
        lines.append(f"{prefix}{connector}{entry.name}{'/' if entry.is_dir() else ''}")
        if entry.is_dir() and depth < _MAX_DEPTH:
            extension = "    " if i == len(entries) - 1 else "│   "
            lines.extend(_build_tree(entry, prefix + extension, depth + 1, patterns))
    return lines


class ListDirTool(BaseTool):
    name = "list_dir"
    description = "List directory contents recursively up to 2 levels deep as a tree."
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Directory path to list. Defaults to current directory.", "default": "."},
        },
        "required": [],
    }

    def execute(self, args: dict[str, Any]) -> str:
        path_str: str = args.get("path", ".")
        path = Path(path_str).expanduser().resolve()
        if not path.exists():
            return f"Error: path not found: {path_str}"
        if not path.is_dir():
            return f"Error: not a directory: {path_str}"

        patterns = _load_gitignore_patterns(str(path))
        lines = [str(path) + "/"] + _build_tree(path, "", 0, patterns)
        return "\n".join(lines)
