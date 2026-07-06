from __future__ import annotations

import sys
import tomllib
from dataclasses import dataclass, fields
from pathlib import Path

_CONFIG_PATH = Path.home() / ".jarvis" / "config.toml"
_PROJECT_CONFIG_NAME = ".jarvis.toml"
_PROJECT_WALK_DEPTH = 5  # cwd + up to 4 parents, same walk as cli._find_jarvis_md


def _find_project_config(start: Path) -> Path | None:
    """Walk from `start` up to 4 parent directories looking for .jarvis.toml."""
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


def _load_toml(path: Path) -> dict:
    """Parse a TOML file into a dict; warns on stderr and returns {} on failure."""
    try:
        return tomllib.loads(path.read_text())
    except (tomllib.TOMLDecodeError, OSError) as e:
        print(f"Warning: could not parse {path}: {e}. Using defaults.", file=sys.stderr)
        return {}


def _extract_overrides(data: dict, scalar_keys: set[str]) -> dict:
    """Pull known top-level scalar keys, plus the [permissions] allow/deny table."""
    overrides = {k: v for k, v in data.items() if k in scalar_keys}
    permissions = data.get("permissions")
    if isinstance(permissions, dict):
        if "allow" in permissions:
            overrides["permission_allow"] = tuple(permissions["allow"])
        if "deny" in permissions:
            overrides["permission_deny"] = tuple(permissions["deny"])
    return overrides


@dataclass(frozen=True)
class Settings:
    auto_mode: bool = False
    max_tool_iterations: int = 40
    autocompact_tokens: int = 25_000
    tool_timeout_secs: int = 60
    theme: str = "monokai"
    # Glob-style patterns matched against "tool_name(args)", e.g. "run_command(git *)".
    permission_allow: tuple[str, ...] = ()
    permission_deny: tuple[str, ...] = ()

    @classmethod
    def load(cls, path: Path | None = None, cwd: Path | None = None) -> "Settings":
        """Load settings: global config overlaid by a per-project config.

        Reads the global TOML file (`path`, defaulting to `~/.jarvis/config.toml`),
        then walks up from `cwd` (defaulting to the current directory) looking for
        `.jarvis.toml` and overlays its values on top — project settings win.
        Missing files -> defaults. Malformed files -> warn on stderr and skip that
        file. Unknown keys are ignored.
        """
        scalar_keys = {f.name for f in fields(cls)} - {"permission_allow", "permission_deny"}
        merged: dict = {}

        global_path = path if path is not None else _CONFIG_PATH
        if global_path.exists():
            merged.update(_extract_overrides(_load_toml(global_path), scalar_keys))

        project_path = _find_project_config(cwd if cwd is not None else Path.cwd())
        if project_path is not None:
            merged.update(_extract_overrides(_load_toml(project_path), scalar_keys))

        return cls(**{**cls().__dict__, **merged})


def _format_toml_value(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    raise TypeError(f"Unsupported TOML value type: {type(value)!r}")


def _dump_toml(data: dict) -> str:
    """Serialize the small subset of TOML this config needs (scalars + a [permissions] table)."""
    lines = [f"{k} = {_format_toml_value(v)}" for k, v in data.items() if k != "permissions"]

    permissions = data.get("permissions")
    if permissions:
        lines.append("")
        lines.append("[permissions]")
        for key in ("allow", "deny"):
            values = permissions.get(key)
            if values:
                items = ", ".join(_format_toml_value(v) for v in values)
                lines.append(f"{key} = [{items}]")

    return "\n".join(lines) + "\n"


def persist_allow_pattern(pattern: str, path: Path | None = None) -> None:
    """Append `pattern` to the global config's `[permissions] allow` list on disk.

    Preserves the rest of the file's contents (best-effort — a malformed existing
    file is treated as empty rather than blocking the write). Creates
    `~/.jarvis/` if needed.
    """
    target = path if path is not None else _CONFIG_PATH
    data = _load_toml(target) if target.exists() else {}

    permissions = dict(data.get("permissions") or {})
    allow = list(permissions.get("allow") or [])
    if pattern not in allow:
        allow.append(pattern)
    permissions["allow"] = allow
    data["permissions"] = permissions

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(_dump_toml(data))
