from __future__ import annotations

import sys
import tomllib
from dataclasses import dataclass, fields
from pathlib import Path

_CONFIG_PATH = Path.home() / ".jarvis" / "config.toml"


@dataclass(frozen=True)
class Settings:
    auto_mode: bool = False
    max_tool_iterations: int = 40
    autocompact_tokens: int = 25_000
    tool_timeout_secs: int = 60
    theme: str = "monokai"

    @classmethod
    def load(cls, path: Path | None = None) -> "Settings":
        """Load settings from a TOML file, falling back to defaults.

        Missing file -> defaults. Malformed file -> warn on stderr + defaults.
        Unknown keys in the file are ignored; known keys overlay the defaults.
        """
        config_path = path if path is not None else _CONFIG_PATH
        if not config_path.exists():
            return cls()

        try:
            data = tomllib.loads(config_path.read_text())
        except (tomllib.TOMLDecodeError, OSError) as e:
            print(f"Warning: could not parse {config_path}: {e}. Using defaults.", file=sys.stderr)
            return cls()

        valid_keys = {f.name for f in fields(cls)}
        overrides = {k: v for k, v in data.items() if k in valid_keys}
        return cls(**{**cls().__dict__, **overrides})
