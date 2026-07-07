from __future__ import annotations

import importlib.util
import os
import sys
from collections import namedtuple

from . import config, mcp_manager

Check = namedtuple("Check", "name status detail")


def run_diagnostics() -> list[Check]:
    checks: list[Check] = []

    checks.append(Check("Python version", "ok", sys.version.split()[0]))

    missing = [k for k in config._REQUIRED if not os.getenv(k)]
    if missing:
        checks.append(Check("Azure credentials", "fail", ", ".join(missing)))
    else:
        checks.append(Check("Azure credentials", "ok", "all required variables set"))

    mgr = mcp_manager.get_active_manager()
    if mgr is None:
        checks.append(Check("MCP servers", "ok", "no MCP servers configured"))
    else:
        count = len(mgr.list_servers())
        status = "ok" if count > 0 else "warn"
        checks.append(Check("MCP servers", status, str(count)))

    for name in ("pytest", "mypy"):
        installed = importlib.util.find_spec(name) is not None
        status = "ok" if installed else "warn"
        detail = "installed" if installed else "not installed"
        checks.append(Check(name, status, detail))

    return checks
