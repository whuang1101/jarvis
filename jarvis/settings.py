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


@dataclass(frozen=True)
class Settings:
    auto_mode: bool = False
    dangerously_skip_permissions: bool = False
    max_tool_iterations: int = 40
    autocompact_tokens: int = 25_000
    tool_timeout_secs: int = 60
    theme: str = "monokai"

    @classmethod
    def load(cls, path: Path | None = None, cwd: Path | None = None) -> "Settings":
        """Load settings: global config overlaid by a per-project config.

        Reads the global TOML file (`path`, defaulting to `~/.jarvis/config.toml`),
        then walks up from `cwd` (defaulting to the current directory) looking for
        `.jarvis.toml` and overlays its values on top — project settings win.
        Missing files -> defaults. Malformed files -> warn on stderr and skip that
        file. Unknown keys are ignored.
        """
        valid_keys = {f.name for f in fields(cls)}
        merged: dict = {}

        global_path = path if path is not None else _CONFIG_PATH
        if global_path.exists():
            merged.update({k: v for k, v in _load_toml(global_path).items() if k in valid_keys})

        project_path = _find_project_config(cwd if cwd is not None else Path.cwd())
        if project_path is not None:
            merged.update({k: v for k, v in _load_toml(project_path).items() if k in valid_keys})

        return cls(**{**cls().__dict__, **merged})
