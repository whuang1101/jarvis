from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import threading
from pathlib import Path
from typing import Any

from .base import BaseTool
from ..formatter import print_streamed_line
from ..settings import Settings
from ..tasks import start_background_task

_TIMEOUT = 120
# Matches `cd` alone (-> home) or `cd <path>`, but NOT commands merely prefixed
# with cd like `cdiff` or `cdr` (the optional group still requires whitespace).
_CD_RE = re.compile(r"^\s*cd(?:\s+(.*?))?\s*$")
_REINSTALL_RE = re.compile(r"pipx\s+reinstall\s+jarvis")


def _build_sandbox_argv(command: str, cwd: str, allow_network: bool) -> list[str]:
    bwrap_path = shutil.which("bwrap")
    if bwrap_path is None:
        return []
    argv = [
        bwrap_path,
        "--ro-bind", "/", "/",
        "--dev", "/dev",
        "--proc", "/proc",
        "--tmpfs", "/tmp",
        "--bind", cwd, cwd,
        "--chdir", cwd,
        "--die-with-parent",
    ]
    if not allow_network:
        argv.append("--unshare-net")
    argv.extend(["/bin/sh", "-c", command])
    return argv


class RunCommandTool(BaseTool):
    name = "run_command"
    description = "Run a shell command and return its stdout and stderr output."
    parameters = {
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "Shell command to execute."},
            "background": {
                "type": "boolean",
                "description": (
                    "If true, launch the command detached and return a task id immediately "
                    "instead of waiting for it to finish. Use task_output to check on it."
                ),
            },
        },
        "required": ["command"],
    }

    def execute(self, args: dict[str, Any]) -> str:
        command: str = args["command"]

        if args.get("background"):
            task_id = start_background_task(command)
            return f"Started background task {task_id}. Use task_output to check its status and log."

        # Handle `cd` by actually changing the process working directory
        m = _CD_RE.match(command)
        if m:
            target = (m.group(1) or "").strip("'\"") or str(Path.home())
            target = os.path.expanduser(target)
            try:
                os.chdir(target)
                return f"Changed directory to {os.getcwd()}"
            except FileNotFoundError:
                return f"Error: no such directory: {target}"
            except Exception as e:
                return f"Error: {e}"

        from ..permissions import is_sandbox

        try:
            if is_sandbox():
                argv = _build_sandbox_argv(command, os.getcwd(), Settings.load().sandbox_allow_network)
                if not argv:
                    return (
                        "Error: sandbox is enabled but 'bwrap' was not found on PATH; "
                        "install bubblewrap or run /sandbox off"
                    )
                proc = subprocess.Popen(
                    argv,
                    shell=False,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    bufsize=1,
                    cwd=os.getcwd(),
                )
            else:
                proc = subprocess.Popen(
                    command,
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    bufsize=1,
                    cwd=os.getcwd(),
                )

            stdout_lines: list[str] = []
            stderr_lines: list[str] = []

            def _stream(pipe, sink: list[str], is_stderr: bool) -> None:
                for line in pipe:
                    sink.append(line)
                    print_streamed_line(line.rstrip("\n"), stderr=is_stderr)
                pipe.close()

            t_out = threading.Thread(target=_stream, args=(proc.stdout, stdout_lines, False))
            t_err = threading.Thread(target=_stream, args=(proc.stderr, stderr_lines, True))
            t_out.start()
            t_err.start()

            try:
                proc.wait(timeout=_TIMEOUT)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
                t_out.join()
                t_err.join()
                return f"Error: command timed out after {_TIMEOUT}s"

            t_out.join()
            t_err.join()

            stdout = "".join(stdout_lines)
            stderr = "".join(stderr_lines)
            returncode = proc.returncode

            parts: list[str] = []
            if stdout:
                parts.append(stdout)
            if stderr:
                parts.append(f"[stderr]\n{stderr}")
            if returncode != 0:
                parts.append(f"[exit code: {returncode}]")
            output = "\n".join(parts) if parts else "(no output)"

            # Auto-restart after a successful pipx reinstall jarvis
            if _REINSTALL_RE.search(command) and returncode == 0:
                # If auto mode is on, write a resume state so the new session
                # picks up where it left off without any user input
                from ..permissions import is_auto_mode, is_dangerously_skip_permissions
                from ..context import is_plan_mode
                if is_auto_mode():
                    resume_path = Path.home() / ".jarvis" / "resume.json"
                    resume_path.parent.mkdir(parents=True, exist_ok=True)
                    resume_path.write_text(json.dumps({
                        "message": "Continue working through TODO.md autonomously. Check for the next uncompleted item, implement it, mark it done, then move to the next. Do not ask to proceed between items.",
                        "auto": True,
                        "dangerously_skip_permissions": is_dangerously_skip_permissions(),
                        "plan": is_plan_mode(),
                    }))
                jarvis_bin = shutil.which("jarvis")
                if jarvis_bin:
                    os.execv(jarvis_bin, [jarvis_bin])

            return output
        except subprocess.TimeoutExpired:
            return f"Error: command timed out after {_TIMEOUT}s"
        except Exception as e:
            return f"Error running command: {e}"
