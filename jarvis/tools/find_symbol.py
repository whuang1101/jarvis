from __future__ import annotations

import re
import subprocess
from typing import Any

from .base import BaseTool

# Trailing \b prevents matching a longer symbol that merely starts with `symbol`
# (e.g. searching "foo" should not match "def foobar"). The symbol is re.escape'd
# before formatting so regex metacharacters in a name are treated literally.
_DEF_PATTERN = r"(def|class|function|async function|const|let|var|type|interface|fn|pub fn|func)\s+{symbol}\b"
_MAX_LINES = 60


class FindSymbolTool(BaseTool):
    name = "find_symbol"
    description = (
        "Find where a function, class, or variable is defined or referenced in the codebase. "
        "Use 'definition' to find where it's declared, 'references' for all usages, 'all' for both."
    )
    parameters = {
        "type": "object",
        "properties": {
            "symbol": {"type": "string", "description": "Symbol name (function, class, variable)."},
            "kind": {
                "type": "string",
                "enum": ["definition", "references", "all"],
                "description": "What to find.",
                "default": "all",
            },
            "directory": {
                "type": "string",
                "description": "Directory to search. Defaults to current directory.",
                "default": ".",
            },
        },
        "required": ["symbol"],
    }

    def execute(self, args: dict[str, Any]) -> str:
        symbol: str = args["symbol"]
        kind: str = args.get("kind", "all")
        directory: str = args.get("directory", ".")
        parts: list[str] = []

        try:
            if kind in ("definition", "all"):
                pattern = _DEF_PATTERN.format(symbol=re.escape(symbol))
                r = subprocess.run(
                    ["grep", "-rn", "-E", pattern, directory],
                    capture_output=True, text=True, timeout=15,
                )
                if r.stdout.strip():
                    parts.append(f"[definitions]\n{r.stdout.strip()}")

            if kind in ("references", "all"):
                r = subprocess.run(
                    ["grep", "-rn", "-w", symbol, directory],
                    capture_output=True, text=True, timeout=15,
                )
                if r.stdout.strip():
                    lines = r.stdout.strip().splitlines()
                    truncated = ""
                    if len(lines) > _MAX_LINES:
                        truncated = f"\n... ({len(lines) - _MAX_LINES} more matches)"
                        lines = lines[:_MAX_LINES]
                    parts.append(f"[references]\n" + "\n".join(lines) + truncated)
        except subprocess.TimeoutExpired:
            return f"Error: search for '{symbol}' timed out after 15s"
        except FileNotFoundError:
            return "Error: grep not found on this system"
        except OSError as e:
            return f"Error searching for '{symbol}': {e}"

        return "\n\n".join(parts) if parts else f"No matches found for '{symbol}'"
