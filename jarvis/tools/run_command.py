from __future__ import annotations

import subprocess
from typing import Any

from .base import BaseTool

_TIMEOUT = 30


class RunCommandTool(BaseTool):
    name = "run_command"
    description = "Run a shell command and return its stdout and stderr output."
    parameters = {
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "Shell command to execute."},
        },
        "required": ["command"],
    }

    def execute(self, args: dict[str, Any]) -> str:
        command: str = args["command"]
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=_TIMEOUT,
            )
            parts: list[str] = []
            if result.stdout:
                parts.append(result.stdout)
            if result.stderr:
                parts.append(f"[stderr]\n{result.stderr}")
            if result.returncode != 0:
                parts.append(f"[exit code: {result.returncode}]")
            return "\n".join(parts) if parts else "(no output)"
        except subprocess.TimeoutExpired:
            return f"Error: command timed out after {_TIMEOUT}s"
        except Exception as e:
            return f"Error running command: {e}"
