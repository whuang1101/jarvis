from __future__ import annotations

import sys
import time
from dataclasses import replace
from types import SimpleNamespace

import jarvis.agent as agent_module
from jarvis.agent import (
    truncate_tool_result,
    execute_with_timeout,
    run_pre_tool_hooks,
    run_post_tool_hooks,
)
from jarvis.context import ContextManager, UsageTracker
from jarvis.tools import get_all_tools
from jarvis.tools.base import BaseTool
from jarvis.tools.read_file import ReadFileTool


class TestTruncateToolResult:
    def test_short_result_unchanged(self):
        assert truncate_tool_result("hello") == "hello"

    def test_long_result_truncated(self):
        result = truncate_tool_result("x" * 50_000)
        assert len(result) < 10_000
        assert "chars omitted" in result
        assert result.startswith("x" * 100)
        assert result.endswith("x" * 100)


class _SleepTool(BaseTool):
    name = "sleep_tool"
    description = "test"
    parameters = {"type": "object", "properties": {}}

    def execute(self, args):
        time.sleep(args.get("secs", 0))
        return "done"


class TestExecuteWithTimeout:
    def test_fast_tool_returns(self):
        assert execute_with_timeout(_SleepTool(), {"secs": 0}, timeout=5) == "done"

    def test_slow_tool_times_out(self):
        result = execute_with_timeout(_SleepTool(), {"secs": 2}, timeout=1)
        assert result.startswith("Error: tool timed out")


class TestReadFileGuards:
    def test_large_file_requires_slice(self, tmp_path):
        f = tmp_path / "big.txt"
        f.write_text("x" * 200_000)
        result = ReadFileTool().execute({"path": str(f)})
        assert result.startswith("Error") and "offset" in result

    def test_large_file_slice_works(self, tmp_path):
        f = tmp_path / "big.txt"
        f.write_text("\n".join(f"line{i}" for i in range(1, 50_001)))
        result = ReadFileTool().execute({"path": str(f), "offset": 100, "limit": 3})
        assert "100: line100" in result
        assert "103" not in result

    def test_offset_past_end(self, tmp_path):
        f = tmp_path / "s.txt"
        f.write_text("one\ntwo\n")
        result = ReadFileTool().execute({"path": str(f), "offset": 99, "limit": 5})
        assert result.startswith("Error")


_BLOCK_SCRIPT = """
import sys, json
data = json.load(sys.stdin)
if data["args"].get("path") == "blocked.txt":
    print("blocked path", file=sys.stderr)
    sys.exit(2)
"""


class TestPreToolHooks:
    def test_blocks_on_exit_code_2(self, tmp_path):
        script = tmp_path / "block.py"
        script.write_text(_BLOCK_SCRIPT)
        hooks = ({"match": "write_file", "run": f"{sys.executable} {script}"},)
        result = run_pre_tool_hooks(hooks, "write_file", {"path": "blocked.txt"})
        assert result == "blocked path"

    def test_allows_when_hook_exits_zero(self, tmp_path):
        script = tmp_path / "block.py"
        script.write_text(_BLOCK_SCRIPT)
        hooks = ({"match": "write_file", "run": f"{sys.executable} {script}"},)
        result = run_pre_tool_hooks(hooks, "write_file", {"path": "ok.txt"})
        assert result is None

    def test_ignores_non_matching_tool(self):
        hooks = ({"match": "read_file", "run": "exit 2"},)
        result = run_pre_tool_hooks(hooks, "write_file", {"path": "blocked.txt"})
        assert result is None

    def test_timeout_blocks_with_message(self):
        hooks = ({"match": "write_file", "run": "sleep 2"},)
        result = run_pre_tool_hooks(hooks, "write_file", {"path": "x"}, timeout=1)
        assert result is not None
        assert "timed out" in result


class TestRunAgentToolOverrides:
    def test_restricted_tool_set_rejects_tools_outside_it_and_returns_final_text(self, monkeypatch):
        calls = {"n": 0}

        def fake_stream_turn(client, context, tracker, tools):
            calls["n"] += 1
            if calls["n"] == 1:
                return "", {0: {"id": "call1", "name": "list_dir", "arguments": "{}"}}, "tool_calls"
            return "done", {}, "stop"

        monkeypatch.setattr(agent_module, "_stream_turn", fake_stream_turn)
        context = ContextManager()
        read_only = [t for t in get_all_tools() if t.name == "read_file"]

        result = agent_module.run_agent(
            "task", client=object(), context=context, tracker=UsageTracker(), tools=read_only
        )

        assert result == "done"
        tool_msgs = [m for m in context._history if m.get("role") == "tool"]
        assert "unknown tool" in tool_msgs[0]["content"]

    def test_allow_subagents_false_strips_spawn_agent_from_default_tools(self, monkeypatch):
        def fake_stream_turn(client, context, tracker, tools):
            assert "spawn_agent" not in {t.name for t in tools}
            return "ok", {}, "stop"

        monkeypatch.setattr(agent_module, "_stream_turn", fake_stream_turn)
        context = ContextManager()

        result = agent_module.run_agent(
            "task", client=object(), context=context, tracker=UsageTracker(), allow_subagents=False
        )

        assert result == "ok"

    def test_max_iterations_override_caps_the_loop(self, monkeypatch):
        calls = {"n": 0}

        def fake_stream_turn(client, context, tracker, tools):
            calls["n"] += 1
            return "", {0: {"id": f"c{calls['n']}", "name": "read_file", "arguments": "{}"}}, "tool_calls"

        monkeypatch.setattr(agent_module, "_stream_turn", fake_stream_turn)
        context = ContextManager()

        agent_module.run_agent(
            "task", client=object(), context=context, tracker=UsageTracker(), max_iterations=2
        )

        # 2 iterations inside the loop + 1 final progress-summary turn after the cap.
        assert calls["n"] == 3


class _FakeStreamClient:
    """Fake JarvisClient: .stream() replays canned chunks, ignoring the request."""

    def __init__(self, chunks):
        self._chunks = chunks

    def stream(self, messages, tools=None):
        return iter(self._chunks)

    def current_deployment(self):
        return "fake-deployment"


def _fake_chunk(content=None, reasoning_content=None, finish_reason=None):
    delta = SimpleNamespace(content=content, tool_calls=None, reasoning_content=reasoning_content)
    choice = SimpleNamespace(delta=delta, finish_reason=finish_reason)
    return SimpleNamespace(choices=[choice], usage=None)


class TestStreamTurnThinking:
    def test_reasoning_excluded_from_full_text_and_captured_in_thinking_buffer(self, monkeypatch):
        monkeypatch.setattr(agent_module, "_settings", replace(agent_module._settings, show_thinking=True))
        captured_thinking = []
        original_render = agent_module.render_thinking_block

        def fake_render_thinking_block(text):
            captured_thinking.append(text)
            return original_render(text)

        monkeypatch.setattr(agent_module, "render_thinking_block", fake_render_thinking_block)

        chunks = [
            _fake_chunk(reasoning_content="Let me "),
            _fake_chunk(reasoning_content="think about this."),
            _fake_chunk(content="The "),
            _fake_chunk(content="answer.", finish_reason="stop"),
        ]
        client = _FakeStreamClient(chunks)

        full_text, tool_calls, finish_reason = agent_module._stream_turn(
            client, ContextManager(), UsageTracker(), []
        )

        assert full_text == "The answer."
        assert "Let me" not in full_text
        assert finish_reason == "stop"
        assert tool_calls == {}
        assert captured_thinking[-1] == "Let me think about this."

    def test_reasoning_dropped_when_show_thinking_disabled(self, monkeypatch):
        monkeypatch.setattr(agent_module, "_settings", replace(agent_module._settings, show_thinking=False))
        thinking_calls = []
        monkeypatch.setattr(agent_module, "print_thinking_header", lambda: thinking_calls.append("header"))
        monkeypatch.setattr(agent_module, "render_thinking_block", lambda text: thinking_calls.append(text))

        chunks = [
            _fake_chunk(reasoning_content="secret reasoning"),
            _fake_chunk(content="answer", finish_reason="stop"),
        ]
        client = _FakeStreamClient(chunks)

        full_text, _, _ = agent_module._stream_turn(client, ContextManager(), UsageTracker(), [])

        assert full_text == "answer"
        assert thinking_calls == []


class TestStreamTurnUsage:
    def test_cached_tokens_recorded_from_prompt_tokens_details(self):
        usage = SimpleNamespace(
            prompt_tokens=1000,
            completion_tokens=100,
            prompt_tokens_details=SimpleNamespace(cached_tokens=600),
        )
        chunk = SimpleNamespace(choices=[], usage=usage)
        client = _FakeStreamClient([chunk])
        tracker = UsageTracker()

        agent_module._stream_turn(client, ContextManager(), tracker, [])

        assert tracker.cached_tokens == 600

    def test_missing_prompt_tokens_details_records_zero_cached_tokens(self):
        usage = SimpleNamespace(prompt_tokens=1000, completion_tokens=100)
        chunk = SimpleNamespace(choices=[], usage=usage)
        client = _FakeStreamClient([chunk])
        tracker = UsageTracker()

        agent_module._stream_turn(client, ContextManager(), tracker, [])

        assert tracker.cached_tokens == 0


class TestPostToolHooks:
    def test_runs_matching_hook_as_side_effect(self, tmp_path):
        marker = tmp_path / "marker.txt"
        hooks = ({"match": "write_file", "run": f"touch {marker}"},)
        run_post_tool_hooks(hooks, "write_file", {"path": "x"})
        assert marker.exists()

    def test_skips_non_matching_tool(self, tmp_path):
        marker = tmp_path / "marker.txt"
        hooks = ({"match": "read_file", "run": f"touch {marker}"},)
        run_post_tool_hooks(hooks, "write_file", {"path": "x"})
        assert not marker.exists()
