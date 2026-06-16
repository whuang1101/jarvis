from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from .base import BaseTool

_TIMEOUT = 120
_CD_RE = re.compile(r"^\s*cd\s+(.*?)\s*$")
_REINSTALL_RE = re.compile(r"pipx\s+reinstall\s+jarvis")


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

        # Handle `cd` by actually changing the process working directory
        m = _CD_RE.match(command)
        if m:
            target = m.group(1).strip("'\"") or str(Path.home())
            target = os.path.expanduser(target)
            try:
                os.chdir(target)
                return f"Changed directory to {os.getcwd()}"
            except FileNotFoundError:
                return f"Error: no such directory: {target}"
            except Exception as e:
                return f"Error: {e}"

        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=_TIMEOUT,
                cwd=os.getcwd(),
            )
            parts: list[str] = []
            if result.stdout:
                parts.append(result.stdout)
            if result.stderr:
                parts.append(f"[stderr]\n{result.stderr}")
            if result.returncode != 0:
                parts.append(f"[exit code: {result.returncode}]")
            output = "\n".join(parts) if parts else "(no output)"

            # Auto-restart after a successful pipx reinstall jarvis
            if _REINSTALL_RE.search(command) and result.returncode == 0:
                jarvis_bin = shutil.which("jarvis")
                if jarvis_bin:
                    os.execv(jarvis_bin, [jarvis_bin])

            return output
        except subprocess.TimeoutExpired:
            return f"Error: command timed out after {_TIMEOUT}s"
        except Exception as e:
            return f"Error running command: {e}"
