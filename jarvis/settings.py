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
    dangerously_skip_permissions: bool = False
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
        settings, _ = cls.load_with_sources(path, cwd)
        return settings

    @classmethod
    def load_with_sources(
        cls, path: Path | None = None, cwd: Path | None = None
    ) -> tuple["Settings", dict[str, str]]:
        """Like `load`, but also reports where each field's effective value came from.

        Returns the merged Settings plus a dict mapping every field name to
        "default", "global", or "project" — whichever file last set it.
        """
        scalar_keys = {f.name for f in fields(cls)} - {"permission_allow", "permission_deny"}
        merged: dict = {}
        sources: dict[str, str] = {f.name: "default" for f in fields(cls)}

        global_path = path if path is not None else _CONFIG_PATH
        if global_path.exists():
            global_overrides = _extract_overrides(_load_toml(global_path), scalar_keys)
            merged.update(global_overrides)
            for key in global_overrides:
                sources[key] = "global"

        project_path = _find_project_config(cwd if cwd is not None else Path.cwd())
        if project_path is not None:
            project_overrides = _extract_overrides(_load_toml(project_path), scalar_keys)
            merged.update(project_overrides)
            for key in project_overrides:
                sources[key] = "project"

        return cls(**{**cls().__dict__, **merged}), sources


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


def persist_setting(key: str, raw_value: str, path: Path | None = None) -> None:
    """Write a scalar setting to the global config, coercing `raw_value` to match
    the field's default type (bool/int/str). Preserves the rest of the file's
    contents, same best-effort semantics as `persist_allow_pattern`.

    Raises ValueError if `key` isn't a known scalar setting (permission lists
    aren't settable this way — use `persist_allow_pattern`).
    """
    scalar_keys = {f.name for f in fields(Settings)} - {"permission_allow", "permission_deny"}
    if key not in scalar_keys:
        raise ValueError(f"Unknown setting: {key!r}. Valid keys: {', '.join(sorted(scalar_keys))}")

    default = getattr(Settings(), key)
    if isinstance(default, bool):
        value: bool | int | str = raw_value.strip().lower() in ("true", "1", "yes", "on")
    elif isinstance(default, int):
        value = int(raw_value)
    else:
        value = raw_value

    target = path if path is not None else _CONFIG_PATH
    data = _load_toml(target) if target.exists() else {}
    data[key] = value

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(_dump_toml(data))
