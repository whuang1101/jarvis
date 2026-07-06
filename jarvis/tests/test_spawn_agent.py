from __future__ import annotations

import jarvis.agent as agent_module
from jarvis.tools.spawn_agent import SpawnAgentTool, _READ_ONLY_TOOL_NAMES


class TestSpawnAgentTool:
    def test_empty_task_is_error(self):
        result = SpawnAgentTool().execute({"task": "  "})
        assert result.startswith("Error")

    def test_no_active_session_is_error(self, monkeypatch):
        monkeypatch.setattr(agent_module, "_current_client", None)
        monkeypatch.setattr(agent_module, "_current_tracker", None)
        result = SpawnAgentTool().execute({"task": "find X"})
        assert "no active agent session" in result

    def test_delegates_to_run_agent_with_read_only_tools_and_no_recursion(self, monkeypatch):
        fake_client = object()
        fake_tracker = object()
        monkeypatch.setattr(agent_module, "_current_client", fake_client)
        monkeypatch.setattr(agent_module, "_current_tracker", fake_tracker)

        captured = {}

        def fake_run_agent(task, client, context, tracker, logger=None, session=None, *, tools=None, max_iterations=None, allow_subagents=True):
            captured["task"] = task
            captured["client"] = client
            captured["tracker"] = tracker
            captured["tools"] = tools
            captured["max_iterations"] = max_iterations
            captured["allow_subagents"] = allow_subagents
            return "final answer"

        monkeypatch.setattr(agent_module, "run_agent", fake_run_agent)

        result = SpawnAgentTool().execute({"task": "find every place plan mode state is read"})

        assert result == "final answer"
        assert captured["task"] == "find every place plan mode state is read"
        assert captured["client"] is fake_client
        assert captured["tracker"] is fake_tracker
        assert captured["max_iterations"] == 25
        assert captured["allow_subagents"] is False
        tool_names = {t.name for t in captured["tools"]}
        assert tool_names == set(_READ_ONLY_TOOL_NAMES)
        assert "write_file" not in tool_names
        assert "edit_file" not in tool_names
        assert "run_command" not in tool_names
        assert "spawn_agent" not in tool_names
