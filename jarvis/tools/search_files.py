from __future__ import annotations

import subprocess
from typing import Any

from .base import BaseTool


class SearchFilesTool(BaseTool):
    name = "search_files"
    description = "Search for a pattern across files using grep. Returns matching lines with file paths and line numbers."
    parameters = {
        "type": "object",
        "properties": {
            "pattern": {"type": "string", "description": "Search pattern (grep regex)."},
            "directory": {"type": "string", "description": "Directory to search in. Defaults to current directory.", "default": "."},
        },
        "required": ["pattern"],
    }

    def execute(self, args: dict[str, Any]) -> str:
        pattern: str = args["pattern"]
        directory: str = args.get("directory", ".")
        try:
            result = subprocess.run(
                ["grep", "-rn", "--include=*", pattern, directory],
                capture_output=True,
                text=True,
                timeout=30,
            )
            output = result.stdout.strip()
            if not output:
                return f"No matches found for '{pattern}' in {directory}"
            lines = output.splitlines()
            if len(lines) > 200:
                return "\n".join(lines[:200]) + f"\n\n[... {len(lines) - 200} more matches truncated]"
            return output
        except subprocess.TimeoutExpired:
            return "Error: search timed out after 30s"
        except Exception as e:
            return f"Error searching files: {e}"
