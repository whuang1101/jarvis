from __future__ import annotations

import subprocess
from typing import Any

from .base import BaseTool

_TIMEOUT = 15


def _git(*args: str) -> tuple[str, int]:
    r = subprocess.run(["git", *args], capture_output=True, text=True, timeout=_TIMEOUT)
    return (r.stdout + r.stderr).strip(), r.returncode


class GitStatusTool(BaseTool):
    name = "git_status"
    description = "Show the working tree status — modified, staged, and untracked files."
    parameters = {"type": "object", "properties": {}, "required": []}

    def execute(self, args: dict[str, Any]) -> str:
        out, code = _git("status")
        return out or ("Not a git repository" if code != 0 else "(clean)")


class GitDiffTool(BaseTool):
    name = "git_diff"
    description = "Show git diff. Unstaged by default; set staged=true for staged changes. Optionally scope to a file or compare against a commit/branch."
    parameters = {
        "type": "object",
        "properties": {
            "staged": {"type": "boolean", "description": "Show staged (index) diff.", "default": False},
            "file": {"type": "string", "description": "Scope diff to this file path."},
            "ref": {"type": "string", "description": "Compare against this commit, branch, or tag (e.g. 'main', 'HEAD~1')."},
        },
        "required": [],
    }

    def execute(self, args: dict[str, Any]) -> str:
        cmd = ["diff"]
        if args.get("staged"):
            cmd.append("--staged")
        if args.get("ref"):
            cmd.append(args["ref"])
        if args.get("file"):
            cmd += ["--", args["file"]]
        out, code = _git(*cmd)
        if code != 0:
            return out or "Error running git diff"
        return out or "(no changes)"


class GitLogTool(BaseTool):
    name = "git_log"
    description = "Show recent git commits with hash, date, message, and author."
    parameters = {
        "type": "object",
        "properties": {
            "n": {"type": "integer", "description": "Number of commits to show (default 10).", "default": 10},
            "file": {"type": "string", "description": "Show only commits that touched this file."},
            "branch": {"type": "string", "description": "Branch to show log for (default: current branch)."},
        },
        "required": [],
    }

    def execute(self, args: dict[str, Any]) -> str:
        n = min(int(args.get("n", 10)), 50)
        cmd = ["log", f"--max-count={n}", "--pretty=format:%C(yellow)%h%Creset %ad  %s  [%an]", "--date=short"]
        if args.get("branch"):
            cmd.append(args["branch"])
        if args.get("file"):
            cmd += ["--", args["file"]]
        out, code = _git(*cmd)
        if code != 0:
            return out or "Error running git log"
        return out or "(no commits)"
