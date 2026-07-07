from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Plugin:
    name: str
    description: str
    version: str
    path: Path


def _plugin_roots() -> tuple[Path, Path]:
    return (Path.home() / ".jarvis" / "plugins", Path.cwd() / ".jarvis" / "plugins")


def _parse(path: Path) -> Plugin | None:
    manifest = path / "plugin.toml"
    try:
        with manifest.open("rb") as f:
            data = tomllib.load(f)
    except (OSError, tomllib.TOMLDecodeError):
        return None

    name = str(data.get("name") or "").strip() or path.name
    description = str(data.get("description") or "")
    version = str(data.get("version") or "")
    return Plugin(name=name, description=description, version=version, path=path)


def discover_plugins() -> list[Plugin]:
    """Discover plugin bundles from the global (~/.jarvis/plugins) and project
    (./.jarvis/plugins) directories. Project plugins override global ones with the same name."""
    plugins: dict[str, Plugin] = {}
    for root in _plugin_roots():
        if not root.is_dir():
            continue
        for entry in root.iterdir():
            if not entry.is_dir():
                continue
            if not (entry / "plugin.toml").is_file():
                continue
            plugin = _parse(entry)
            if plugin is not None:
                plugins[plugin.name] = plugin
    return sorted(plugins.values(), key=lambda p: p.name)
