from __future__ import annotations

from typing import Any

from .base import BaseTool

# Tools safe to hand to a subagent: read/search only, nothing that writes files,
# runs commands, or touches background tasks.
_READ_ONLY_TOOL_NAMES = (
    "read_file",
    "list_dir",
    "search_files",
    "find_symbol",
    "fetch_url",
    "web_search",
    "web_extract",
    "package_info",
    "git_status",
    "git_diff",
    "git_log",
)
_MAX_SUBAGENT_ITERATIONS = 25


class SpawnAgentTool(BaseTool):
    name = "spawn_agent"
    description = (
        "Delegate a self-contained investigation (e.g. 'find every place X is used or defined') "
        "to a read-only subagent that runs in its own context and reports back only its final "
        "answer. Use this for broad codebase searches instead of doing them yourself, so your own "
        "context stays small. The subagent cannot write files, run commands, or spawn further "
        "subagents — give it a fully self-contained task description since it can't ask you for "
        "clarification."
    )
    parameters = {
        "type": "object",
        "properties": {
            "task": {
                "type": "string",
                "description": "The self-contained question or search task for the subagent to investigate.",
            },
        },
        "required": ["task"],
    }

    def execute(self, args: dict[str, Any]) -> str:
        task = str(args.get("task", "")).strip()
        if not task:
            return "Error: task must be a non-empty string"

        from . import get_tool_by_name  # deferred: tools/__init__ is still building _REGISTRY on import
        from .. import agent as agent_module
        from ..context import ContextManager

        if agent_module._current_client is None or agent_module._current_tracker is None:
            return "Error: no active agent session to spawn a subagent from"

        tools = [t for t in (get_tool_by_name(n) for n in _READ_ONLY_TOOL_NAMES) if t is not None]
        sub_context = ContextManager()
        return agent_module.run_agent(
            task,
            agent_module._current_client,
            sub_context,
            agent_module._current_tracker,
            tools=tools,
            max_iterations=_MAX_SUBAGENT_ITERATIONS,
            allow_subagents=False,
        )
