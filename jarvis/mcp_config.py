"""Load MCP server definitions from Claude-Code-compatible `.mcp.json` files."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_GLOBAL_CONFIG = Path.home() / ".jarvis" / "mcp.json"
_PROJECT_CONFIG_NAME = ".mcp.json"
_PROJECT_WALK_DEPTH = 5


def _read_mcp_servers(path: Path) -> dict[str, Any]:
    """Parse `path` as `{"mcpServers": {...}}`, returning {} on any failure."""
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(data, dict):
        return {}
    servers = data.get("mcpServers")
    if not isinstance(servers, dict):
        return {}
    return servers


def _find_project_config(start: Path) -> Path | None:
    """Walk from `start` up to 4 parent directories looking for .mcp.json."""
    path = start
    for _ in range(_PROJECT_WALK_DEPTH):
        candidate = path / _PROJECT_CONFIG_NAME
        if candidate.exists():
            return candidate
        parent = path.parent
        if parent == path:
            break
        path = parent
    return None


def load_mcp_servers(cwd: str | None = None) -> list[dict[str, Any]]:
    """Merge global `~/.jarvis/mcp.json` with a project `.mcp.json` (project wins).

    Returns a list of `{"name", "command", "args", "env"}` dicts for every entry
    with a non-empty `command`; best-effort, never raises.
    """
    merged: dict[str, Any] = {}
    merged.update(_read_mcp_servers(_GLOBAL_CONFIG))

    start = Path(cwd) if cwd is not None else Path.cwd()
    project_config = _find_project_config(start)
    if project_config is not None:
        merged.update(_read_mcp_servers(project_config))

    servers = []
    for name, entry in merged.items():
        if not isinstance(entry, dict):
            continue
        command = entry.get("command")
        if not command:
            continue
        servers.append({
            "name": name,
            "command": command,
            "args": entry.get("args") or [],
            "env": entry.get("env") or {},
        })
    return servers
