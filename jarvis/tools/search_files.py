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

        from .sensitive import _SENSITIVE_GLOBS, is_sensitive_path
        from ..permissions import is_dangerously_skip_permissions

        skip_sensitive = not is_dangerously_skip_permissions()
        cmd = ["grep", "-rn", "--include=*"]
        if skip_sensitive:
            cmd += [f"--exclude={glob}" for glob in _SENSITIVE_GLOBS]
        cmd += [pattern, directory]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
            )
            output = result.stdout.strip()
            if not output:
                return f"No matches found for '{pattern}' in {directory}"
            lines = output.splitlines()
            if skip_sensitive:
                lines = [line for line in lines if not is_sensitive_path(line.split(":", 1)[0])]
            if not lines:
                return f"No matches found for '{pattern}' in {directory}"
            if len(lines) > 200:
                return "\n".join(lines[:200]) + f"\n\n[... {len(lines) - 200} more matches truncated]"
            return "\n".join(lines)
        except subprocess.TimeoutExpired:
            return "Error: search timed out after 30s"
        except Exception as e:
            return f"Error searching files: {e}"
